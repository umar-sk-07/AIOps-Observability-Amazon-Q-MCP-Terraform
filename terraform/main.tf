# =============================================================================
# MAIN INFRASTRUCTURE RESOURCES
# =============================================================================

# =============================================================================
# VPC CONFIGURATION
# =============================================================================

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.cluster_name}-vpc"
  cidr = var.vpc_cidr

  azs             = local.azs
  public_subnets  = local.public_subnets
  private_subnets = local.private_subnets

  # NAT Gateway configuration
  enable_nat_gateway = true
  single_nat_gateway = var.enable_single_nat_gateway

  # Internet Gateway
  create_igw = true

  # DNS configuration
  enable_dns_hostnames = true
  enable_dns_support   = true

  # Manage default resources for better control
  manage_default_network_acl    = true
  default_network_acl_tags      = { Name = "${var.cluster_name}-default-nacl" }
  manage_default_route_table    = true
  default_route_table_tags      = { Name = "${var.cluster_name}-default-rt" }
  manage_default_security_group = true
  default_security_group_tags   = { Name = "${var.cluster_name}-default-sg" }

  # Apply Kubernetes-specific tags to subnets
  public_subnet_tags  = merge(local.common_tags, local.public_subnet_tags)
  private_subnet_tags = merge(local.common_tags, local.private_subnet_tags)

  tags = local.common_tags
}

# =============================================================================
# EKS CLUSTER CONFIGURATION
# =============================================================================

module "retail_app_eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.31"

  # Basic cluster configuration
  cluster_name    = local.cluster_name
  cluster_version = var.kubernetes_version

  # Cluster access configuration
  cluster_endpoint_public_access           = true
  cluster_endpoint_private_access          = true
  enable_cluster_creator_admin_permissions = true

  # EKS Auto Mode configuration - simplified node management
  cluster_compute_config = {
    enabled    = true
    node_pools = ["general-purpose"]
  }

  # Network configuration
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # KMS configuration to avoid conflicts
  create_kms_key = true
  kms_key_description = "EKS cluster ${local.cluster_name} encryption key"
  kms_key_deletion_window_in_days = 7
  
  # Cluster logging (optional - can be expensive)
  cluster_enabled_log_types = []

  tags = local.common_tags
}

# =============================================================================
# EKS ACCESS CONFIGURATION FOR EC2
# =============================================================================

# Grant EC2 instance admin access to EKS cluster
resource "aws_eks_access_entry" "ai_server_admin" {
  cluster_name  = module.retail_app_eks.cluster_name
  principal_arn = aws_iam_role.ai_server_role.arn
  type          = "STANDARD"

  tags = merge(
    local.common_tags,
    {
      Name = "${var.cluster_name}-ai-server-access"
    }
  )

  depends_on = [
    module.retail_app_eks,
    aws_iam_role.ai_server_role
  ]
}

# Associate EKS Cluster Admin Policy to EC2 instance
resource "aws_eks_access_policy_association" "ai_server_admin_policy" {
  cluster_name  = module.retail_app_eks.cluster_name
  principal_arn = aws_iam_role.ai_server_role.arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }

  depends_on = [aws_eks_access_entry.ai_server_admin]
}

# =============================================================================
# EC2 INSTANCE CONFIGURATION
# =============================================================================

# Data source to get the latest Amazon Linux 2023 AMI
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# AWS Key Pair for SSH access
resource "aws_key_pair" "ec2_ai_key" {
  key_name   = "${var.cluster_name}-ec2-ai-key"
  public_key = file("${path.module}/ec2-ai.pub")

  tags = merge(
    local.common_tags,
    {
      Name = "${var.cluster_name}-ec2-ai-key"
    }
  )
}

# Security group for EC2 instance
resource "aws_security_group" "ai_server_sg" {
  name_prefix = "${var.cluster_name}-ai-server-"
  description = "Security group for AI server EC2 instance"
  vpc_id      = module.vpc.vpc_id

  # SSH access
  ingress {
    description = "SSH access"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # Consider restricting this to your IP
  }

  # Webhook receiver port (for AlertManager)
  ingress {
    description = "Webhook receiver from EKS cluster"
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr] # Allow from VPC
  }

  # HTTP access
  ingress {
    description = "HTTP access"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTPS access
  ingress {
    description = "HTTPS access"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Outbound traffic
  egress {
    description = "Allow all outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${var.cluster_name}-ai-server-sg"
    }
  )
}

# IAM role for EC2 instance with EKS access
resource "aws_iam_role" "ai_server_role" {
  name_prefix = "${var.cluster_name}-ai-server-"
  description = "IAM role for AI server EC2 instance with EKS access"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(
    local.common_tags,
    {
      Name = "${var.cluster_name}-ai-server-role"
    }
  )
}

# IAM policy for EKS access
resource "aws_iam_role_policy" "ai_server_eks_policy" {
  name_prefix = "${var.cluster_name}-ai-server-eks-"
  role        = aws_iam_role.ai_server_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster",
          "eks:ListClusters",
          "eks:DescribeNodegroup",
          "eks:ListNodegroups",
          "eks:AccessKubernetesApi"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeSubnets",
          "ec2:DescribeVpcs"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Attach SSM managed policy for Session Manager access
resource "aws_iam_role_policy_attachment" "ai_server_ssm" {
  role       = aws_iam_role.ai_server_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Instance profile for EC2
resource "aws_iam_instance_profile" "ai_server_profile" {
  name_prefix = "${var.cluster_name}-ai-server-"
  role        = aws_iam_role.ai_server_role.name

  tags = merge(
    local.common_tags,
    {
      Name = "${var.cluster_name}-ai-server-profile"
    }
  )
}

# EC2 instance
resource "aws_instance" "ai_server" {
  ami           = data.aws_ami.amazon_linux_2023.id
  instance_type = "t3.micro" # Cost-effective for portfolio

  # SSH key pair
  key_name = aws_key_pair.ec2_ai_key.key_name

  # Network configuration
  subnet_id                   = module.vpc.public_subnets[0]
  vpc_security_group_ids      = [aws_security_group.ai_server_sg.id]
  associate_public_ip_address = true

  # IAM configuration
  iam_instance_profile = aws_iam_instance_profile.ai_server_profile.name

  # Storage configuration
  root_block_device {
    volume_size           = 30
    volume_type           = "gp3"
    delete_on_termination = true
    encrypted             = true
  }

  # Wait for IAM role to be ready
  depends_on = [
    aws_iam_role_policy.ai_server_eks_policy,
    aws_iam_role_policy_attachment.ai_server_ssm,
    aws_key_pair.ec2_ai_key
  ]

  tags = merge(
    local.common_tags,
    {
      Name = "${var.cluster_name}-ai-server"
      Role = "AIOps-Webhook-Receiver"
    }
  )
}
