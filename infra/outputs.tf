output "url"     { value = "http://${aws_lb.app.dns_name}" }
output "ecr_url" { value = aws_ecr_repository.app.repository_url }
output "tabla"   { value = aws_dynamodb_table.diagnosticos.name }