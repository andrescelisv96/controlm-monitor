terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" { region = var.region }

locals { nombre = "controlm-${var.ambiente}" }   # controlm-dev o controlm-prod

# ---------- Red: usamos la red por defecto de tu cuenta ----------
data "aws_vpc" "default" { default = true }
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# ---------- 1. Repositorio de imágenes (ECR) ----------
resource "aws_ecr_repository" "app" {
  name         = local.nombre
  force_delete = true
}

# ---------- 2. Tabla DynamoDB ----------
resource "aws_dynamodb_table" "diagnosticos" {
  name         = "diagnosticos-${var.ambiente}"
  billing_mode = "PAY_PER_REQUEST"               # pagas solo por uso
  hash_key     = "pk"
  range_key    = "fecha"
  attribute {
    name = "pk"
    type = "S"
  }
  attribute {
    name = "fecha"
    type = "S"
  }
}

# ---------- 3. La clave de Gemini en Secrets Manager ----------
resource "aws_secretsmanager_secret" "gemini" {
  name                    = "${local.nombre}-gemini"
  recovery_window_in_days = 0                    # se puede borrar al instante
}
resource "aws_secretsmanager_secret_version" "gemini" {
  secret_id     = aws_secretsmanager_secret.gemini.id
  secret_string = var.gemini_api_key
}

# ---------- 4. Permisos (IAM) ----------
# Rol para que ECS pueda bajar la imagen, leer el secreto y escribir logs
resource "aws_iam_role" "ejecucion" {
  name = "${local.nombre}-ejecucion"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}
resource "aws_iam_role_policy_attachment" "ejecucion" {
  role       = aws_iam_role.ejecucion.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}
resource "aws_iam_role_policy" "leer_secreto" {
  role = aws_iam_role.ejecucion.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = aws_secretsmanager_secret.gemini.arn
    }]
  })
}

# Rol que usa TU APP por dentro: solo puede tocar su tabla
resource "aws_iam_role" "app" {
  name               = "${local.nombre}-app"
  assume_role_policy = aws_iam_role.ejecucion.assume_role_policy
}
resource "aws_iam_role_policy" "dynamo" {
  role = aws_iam_role.app.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["dynamodb:PutItem", "dynamodb:Query", "dynamodb:Scan"]
      Resource = aws_dynamodb_table.diagnosticos.arn
    }]
  })
}

# ---------- 5. Logs (CloudWatch) ----------
resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${local.nombre}"
  retention_in_days = 7                          # borra logs viejos y no cobra de más
}

# ---------- 6. Firewalls (security groups) ----------
resource "aws_security_group" "alb" {
  name   = "${local.nombre}-alb"
  vpc_id = data.aws_vpc.default.id
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]                  # el público entra al load balancer
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_security_group" "app" {
  name   = "${local.nombre}-app"
  vpc_id = data.aws_vpc.default.id
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]  # solo el load balancer llega a la app
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ---------- 7. Load Balancer: reparte el tráfico entre copias ----------
resource "aws_lb" "app" {
  name               = local.nombre
  load_balancer_type = "application"
  subnets            = data.aws_subnets.default.ids
  security_groups    = [aws_security_group.alb.id]
}
resource "aws_lb_target_group" "app" {
  name        = local.nombre
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.default.id
  target_type = "ip"
  health_check { path = "/salud" }               # usa tu endpoint de salud
}
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# ---------- 8. ECS: corre tus contenedores ----------
resource "aws_ecs_cluster" "app" { name = local.nombre }

resource "aws_ecs_task_definition" "app" {
  family                   = local.nombre
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256                 # 0.25 vCPU
  memory                   = 512                 # 0.5 GB
  execution_role_arn       = aws_iam_role.ejecucion.arn
  task_role_arn            = aws_iam_role.app.arn
  container_definitions = jsonencode([{
    name         = "app"
    image        = "${aws_ecr_repository.app.repository_url}:latest"
    portMappings = [{ containerPort = 8000 }]
    environment = [
      { name = "TABLA", value = aws_dynamodb_table.diagnosticos.name },
      { name = "AWS_REGION", value = var.region }
    ]
    secrets = [
      { name = "GOOGLE_API_KEY", valueFrom = aws_secretsmanager_secret.gemini.arn }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "app"
      }
    }
  }])
}

resource "aws_ecs_service" "app" {
  name            = local.nombre
  cluster         = aws_ecs_cluster.app.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.copias                   # 1 en dev, 2 en prod
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = true
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = 8000
  }
  depends_on = [aws_lb_listener.http]
}