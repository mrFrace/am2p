terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
variable "AWS_ACCESS_KEY_ID" {
  type      = string
  sensitive = true
}
variable "AWS_ACCESS_SECRET_ID" {
  type      = string
  sensitive = true
}
variable "mssql_login_pwd" {
  type      = string
  sensitive = true
}
provider "aws" {
  region = "eu-central-1"
  access_key = var.AWS_ACCESS_KEY_ID
  secret_key = var.AWS_ACCESS_SECRET_ID
}

data "aws_eips" "helper_eips" {
  tags = {
    helper = true
  }
}

# VPC EIPs.
output "allocation_ids" {
  value = data.aws_eips.helper_eips.allocation_ids
}

# EC2-Classic EIPs.
output "public_ips" {
  value = data.aws_eips.helper_eips.public_ips
}

#output "allocation_id_helper_eip" {
#  value = allocation_ids.externalIP.id
#}


resource "aws_vpc" "helper_vpc" {
  cidr_block = "192.168.69.0/24"
  tags = {
    Name = "helper_vpc"
    helper = "true"
  }
}

# Create Subnet

resource "aws_subnet" "helper_subnet" {
  vpc_id     = aws_vpc.helper_vpc.id
  cidr_block = "192.168.69.0/27"
  tags = {
    Name = "helper_subnet"
    helper = "true"
  }
}

# Create Internet Gateway

resource "aws_internet_gateway" "helper_igw" {
  vpc_id = aws_vpc.helper_vpc.id
  tags = {
    Name = "helper_igw"
    helper = "true"
  }
}

# Attach Internet Gateway to VPC


# Create Route Table

resource "aws_route_table" "helper_route_table" {
  vpc_id = aws_vpc.helper_vpc.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.helper_igw.id
  }
  tags = {
    Name = "helper_route_table"
    helper = "true"
  }
}

# Associate Subnet with Route Table

resource "aws_route_table_association" "helper_association" {
  subnet_id      = aws_subnet.helper_subnet.id
  route_table_id = aws_route_table.helper_route_table.id
}

# Create Security Group

resource "aws_security_group" "helper_security_group" {
  name_prefix = "helper_security_group"
  description = "Allow SSH access from public IP addresses"
  vpc_id = aws_vpc.helper_vpc.id
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port = 25
    to_port = 25
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow SMTP traffic"
  }

  ingress {
    from_port = 80
    to_port = 80
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow HTTP traffic"
  }

  ingress {
    from_port = 443
    to_port = 443
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow HTTPS traffic"
  }
  egress {
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }
  tags = {
    Name = "helper_security_group"
    helper = "true"
  }
}

# Create Ubuntu Server

resource "aws_instance" "helper_instance" {
  ami           = "ami-097ff5290bf01df68"
  instance_type = "t2.medium"
  key_name      = "mrfrace"
  subnet_id     = aws_subnet.helper_subnet.id
  vpc_security_group_ids = [aws_security_group.helper_security_group.id]
  user_data = <<-EOF
              #!/bin/bash
              sudo apt update
              sudo apt upgrade
              EOF
  tags = {
    Name = "helper_instance"
    helper = "true"
  }
}
