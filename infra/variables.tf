variable "ambiente" { type = string }            # "dev" o "prod"
variable "region"   { default = "us-east-1" }
variable "gemini_api_key" {
  type      = string
  sensitive = true                               # nunca se muestra en pantalla
}
variable "copias"   { default = 1 }              # cuántos contenedores corren