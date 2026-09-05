# Project Vulcan: Seed Terraform Stack - Cross-Account VPC Peering Connection
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60.0"
    }
  }
}

variable "peer_vpc_id" {
  type        = string
  description = "Target Peer VPC ID"
}

variable "peer_cidr" {
  type        = string
  description = "Destination CIDR block for cross-VPC routing"
}

resource "aws_vpc_peering_connection" "peer" {
  peer_vpc_id = var.peer_vpc_id
  vpc_id      = "vpc-0123456789pncroot"
  auto_accept = true

  tags = {
    Environment = "production"
    ManagedBy   = "vulcan-control-plane"
  }
}

resource "aws_route" "peer_route" {
  route_table_id            = "rtb-0987654321pnc"
  destination_cidr_block    = var.peer_cidr
  vpc_peering_connection_id = aws_vpc_peering_connection.peer.id
}
