# Retail Store Sample App - Project Context for Claude AI

## 🎯 Project Overview

This is a **cloud-native microservices retail store application** designed to demonstrate modern DevOps practices on AWS. It showcases:

- **Microservices Architecture**: Multiple independent services working together
- **GitOps Deployment**: Automated deployment using ArgoCD
- **Infrastructure as Code**: Complete AWS infrastructure managed with Terraform
- **Container Orchestration**: Kubernetes (Amazon EKS) with Auto Mode
- **CI/CD Pipeline**: Automated builds and deployments with GitHub Actions
- **Cloud-Native Patterns**: Service mesh, observability, and scalability

---

## 🏗️ Architecture Overview

### Application Architecture

The application consists of **5 microservices** that work together to provide a complete retail store experience:

```
┌─────────────────────────────────────────────────────────────┐
│                        Internet                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   NGINX Ingress      │
              │   Load Balancer      │
              └──────────┬───────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
    ┌────────┐     ┌─────────┐    ┌──────────┐
    │   UI   │────▶│ Catalog │    │   Cart   │
    │ (Java) │     │  (Go)   │    │  (Java)  │
    └────┬───┘     └────┬────┘    └────┬─────┘
         │              │              │
         │              ▼              ▼
         │         ┌────────┐    ┌──────────┐
         └────────▶│Checkout│───▶│  Orders  │
                   │(Node.js)│    │  (Java)  │
                   └────────┘    └──────────┘
                        │              │
                        ▼              ▼
                   ┌────────┐    ┌──────────┐
                   │ Redis  │    │PostgreSQL│
                   └────────┘    └──────────┘
```

### Infrastructure Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      AWS Cloud                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    VPC (10.0.0.0/16)                  │  │
│  │                                                        │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │  │
│  │  │ Public Subnet│  │ Public Subnet│  │Public Subnet│ │  │
│  │  │   AZ-1       │  │   AZ-2       │  │   AZ-3      │ │  │
│  │  │  NAT Gateway │  │              │  │             │ │  │
│  │  └──────┬───────┘  └──────────────┘  └─────────────┘ │  │
│  │         │                                             │  │
│  │  ┌──────┴────────┐  ┌──────────────┐  ┌─────────────┐ │  │
│  │  │Private Subnet │  │Private Subnet│  │Private Subnet│ │
│  │  │   AZ-1        │  │   AZ-2       │  │   AZ-3      │ │  │
│  │  │               │  │              │  │             │ │  │
│  │  │  ┌─────────────────────────────────────────────┐ │ │  │
│  │  │  │         EKS Cluster (Auto Mode)             │ │ │  │
│  │  │  │                                              │ │ │  │
│  │  │  │  ┌──────────┐  ┌──────────┐  ┌───────────┐ │ │ │  │
│  │  │  │  │  ArgoCD  │  │  NGINX   │  │Cert-Manager│ │ │  │
│  │  │  │  └──────────┘  └──────────┘  └───────────┘ │ │ │  │
│  │  │  │                                              │ │ │  │
│  │  │  │  ┌────────────────────────────────────────┐ │ │ │  │
│  │  │  │  │    Retail Store Microservices          │ │ │ │  │
│  │  │  │  │  UI | Catalog | Cart | Orders | Checkout│ │ │ │  │
│  │  │  │  └────────────────────────────────────────┘ │ │ │  │
│  │  │  └─────────────────────────────────────────────┘ │ │  │
│  │  └──────────────┘  └──────────────┘  └─────────────┘ │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Microservices Details

### 1. **UI Service** (Frontend)
- **Language**: Java (Spring Boot)
- **Purpose**: Web interface for the retail store
- **Port**: 8080
- **Dependencies**: Catalog, Cart, Orders, Checkout APIs
- **Features**:
  - Product browsing interface
  - Shopping cart management UI
  - Order placement interface
  - Multiple theme support (default, green, orange)
  - Optional AI chatbot integration (Bedrock/OpenAI)
- **Image**: `public.ecr.aws/aws-containers/retail-store-sample-ui:1.2.2`
- **Location**: `src/ui/`

### 2. **Catalog Service** (Product Catalog)
- **Language**: Go
- **Purpose**: Product catalog API
- **Port**: 8080
- **Database**: MySQL
- **Features**:
  - Product listing and search
  - Product details retrieval
  - In-memory or MySQL persistence
  - Chaos engineering endpoints
- **Image**: `public.ecr.aws/aws-containers/retail-store-sample-catalog:1.2.2`
- **Location**: `src/catalog/`

### 3. **Cart Service** (Shopping Cart)
- **Language**: Java (Spring Boot)
- **Purpose**: Shopping cart management API
- **Port**: 8080
- **Database**: Amazon DynamoDB
- **Features**:
  - Add/remove items from cart
  - Cart persistence per user
  - In-memory or DynamoDB persistence
  - Chaos engineering endpoints
- **Image**: `public.ecr.aws/aws-containers/retail-store-sample-cart:1.2.2`
- **Location**: `src/cart/`

### 4. **Checkout Service** (Checkout Orchestration)
- **Language**: Node.js (NestJS)
- **Purpose**: Checkout process orchestration
- **Port**: 8080
- **Database**: Redis
- **Features**:
  - Checkout session management
  - Shipping options
  - Order submission to Orders service
  - In-memory or Redis persistence
- **Image**: `public.ecr.aws/aws-containers/retail-store-sample-checkout:1.2.2`
- **Location**: `src/checkout/`

### 5. **Orders Service** (Order Management)
- **Language**: Java (Spring Boot)
- **Purpose**: Order management and persistence
- **Port**: 8080
- **Database**: PostgreSQL
- **Messaging**: RabbitMQ or Amazon SQS
- **Features**:
  - Order creation and storage
  - Order history retrieval
  - Event publishing for order events
  - In-memory or PostgreSQL persistence
- **Image**: `public.ecr.aws/aws-containers/retail-store-sample-orders:1.2.2`
- **Location**: `src/orders/`

---

## 🔄 Branching Strategy & GitOps Workflow

This project implements a **dual-branch strategy** for different deployment scenarios:

### 🌐 **Main Branch** (Public Application)
- **Purpose**: Simple deployment for demos, learning, and quick testing
- **Images**: Public ECR with stable versions (v1.2.2)
- **Deployment**: Manual control using umbrella Helm chart
- **ArgoCD**: Single application (`retail-store-app`)
- **Updates**: Manual only
- **CI/CD**: No GitHub Actions workflows
- **Best For**: Demos, learning, prototyping, simple deployments

### 🏭 **GitOps Branch** (Production)
- **Purpose**: Full production workflow with automated CI/CD
- **Images**: Private ECR with commit-hash tags
- **Deployment**: Automated via GitHub Actions
- **ArgoCD**: Individual applications per service
- **Updates**: Automatic on code changes
- **CI/CD**: Complete GitHub Actions pipeline
- **Best For**: Production environments, enterprise deployments

### GitOps Workflow (Production Branch)

```
Developer Commits → GitHub Actions Triggered → Build Docker Images
                                              ↓
                                    Push to Private ECR
                                              ↓
                                    Update Helm Chart Values
                                              ↓
                                    Commit Changes to Git
                                              ↓
                                    ArgoCD Detects Changes
                                              ↓
                                    Auto-Sync to Kubernetes
```

---

## 🛠️ Infrastructure Components

### Terraform Infrastructure (`terraform/`)

The infrastructure is fully automated using Terraform with the following components:

#### **Core Infrastructure** (`main.tf`)
- **VPC**: Custom VPC with CIDR 10.0.0.0/16
  - 3 Availability Zones for high availability
  - Public subnets for load balancers
  - Private subnets for EKS nodes
  - NAT Gateway for outbound internet access
  - Internet Gateway for public access

- **EKS Cluster**: Amazon EKS with Auto Mode
  - Kubernetes version: 1.33
  - Auto Mode: Simplified node management
  - Compute: General-purpose node pools
  - Endpoint: Public and private access
  - KMS encryption for cluster secrets

#### **Security** (`security.tf`)
- Security groups for cluster access
- IAM roles and policies
- Network ACLs
- KMS encryption keys

#### **Add-ons** (`addons.tf`)
- **NGINX Ingress Controller**: Load balancing and routing
- **Cert Manager**: Automatic SSL certificate management
- **Let's Encrypt**: Free SSL certificates

#### **ArgoCD** (`argocd.tf`)
- GitOps deployment automation
- Application sync and health monitoring
- Automated rollbacks
- Web UI for deployment visualization

### Kubernetes Resources

#### **ArgoCD Applications** (`argocd/applications/`)
Each microservice has its own ArgoCD application:
- `retail-store-ui.yaml`
- `retail-store-catalog.yaml`
- `retail-store-cart.yaml`
- `retail-store-checkout.yaml`
- `retail-store-orders.yaml`

#### **ArgoCD Project** (`argocd/projects/`)
- `retail-store-project.yaml`: Defines permissions and resources

#### **Helm Charts** (`src/*/chart/`)
Each service has its own Helm chart with:
- Deployment configurations
- Service definitions
- ConfigMaps and Secrets
- Ingress rules
- HPA (Horizontal Pod Autoscaler) settings
- PDB (Pod Disruption Budget) settings

---

## 🚀 Deployment Process

### Prerequisites
1. **AWS CLI** v2+ configured with credentials
2. **Terraform** 1.0+
3. **kubectl** 1.33+
4. **Docker** 20.0+
5. **Helm** 3.0+
6. **Git** 2.0+

### Step-by-Step Deployment

#### 1. **Clone Repository**
```bash
git clone https://github.com/umar-sk-07/AIOps-Observability-Amazon-Q-MCP-Terraform.git
cd AIOps-Observability-Amazon-Q-MCP-Terraform
```

#### 2. **Choose Branch Strategy**
- **For simple deployment**: Stay on `main` branch
- **For production with CI/CD**: Switch to `gitops` branch

#### 3. **Deploy Infrastructure**
```bash
cd terraform/
terraform init
terraform apply --auto-approve
```

This creates:
- VPC with networking
- EKS cluster
- ArgoCD
- NGINX Ingress Controller
- Cert Manager

#### 4. **Configure kubectl**
```bash
aws eks update-kubeconfig --name retail-store --region <region>
```

#### 5. **Access ArgoCD**
```bash
# Get admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d

# Port-forward to UI
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Open browser: https://localhost:8080
# Username: admin
# Password: <from above command>
```

#### 6. **Access Application**
```bash
# Get load balancer URL
kubectl get svc -n ingress-nginx

# Use EXTERNAL-IP to access the retail store
```

#### 7. **GitHub Actions Setup** (GitOps Branch Only)
Configure GitHub secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `AWS_ACCOUNT_ID`

---

## 📁 Project Structure

```
retail-store-sample-app/
├── .git/                           # Git repository
├── .github/                        # GitHub Actions workflows (gitops branch)
│   └── workflows/
│       └── deploy.yml              # CI/CD pipeline
├── argocd/                         # ArgoCD configurations
│   ├── applications/               # Application definitions
│   │   ├── retail-store-ui.yaml
│   │   ├── retail-store-catalog.yaml
│   │   ├── retail-store-cart.yaml
│   │   ├── retail-store-checkout.yaml
│   │   └── retail-store-orders.yaml
│   └── projects/
│       └── retail-store-project.yaml
├── docs/                           # Documentation and images
│   └── images/
├── src/                            # Source code for all services
│   ├── app/                        # Umbrella Helm chart
│   │   └── chart/
│   ├── ui/                         # UI Service (Java)
│   │   ├── src/
│   │   ├── chart/                  # Helm chart
│   │   ├── Dockerfile
│   │   ├── pom.xml
│   │   └── README.md
│   ├── catalog/                    # Catalog Service (Go)
│   │   ├── api/
│   │   ├── chart/                  # Helm chart
│   │   ├── Dockerfile
│   │   ├── go.mod
│   │   └── README.md
│   ├── cart/                       # Cart Service (Java)
│   │   ├── src/
│   │   ├── chart/                  # Helm chart
│   │   ├── Dockerfile
│   │   ├── pom.xml
│   │   └── README.md
│   ├── checkout/                   # Checkout Service (Node.js)
│   │   ├── src/
│   │   ├── chart/                  # Helm chart
│   │   ├── Dockerfile
│   │   ├── package.json
│   │   └── README.md
│   └── orders/                     # Orders Service (Java)
│       ├── src/
│       ├── chart/                  # Helm chart
│       ├── Dockerfile
│       ├── pom.xml
│       └── README.md
├── terraform/                      # Infrastructure as Code
│   ├── main.tf                     # VPC and EKS cluster
│   ├── variables.tf                # Input variables
│   ├── outputs.tf                  # Output values
│   ├── versions.tf                 # Provider versions
│   ├── locals.tf                   # Local values
│   ├── security.tf                 # Security groups
│   ├── addons.tf                   # EKS add-ons
│   ├── argocd.tf                   # ArgoCD installation
│   └── README.md
├── BRANCHING_STRATEGY.md           # Detailed branching guide
├── README.md                       # Main documentation
├── LICENSE                         # Apache 2.0 license
└── .gitignore
```

---

## 🔧 Configuration & Environment Variables

### UI Service Configuration
```yaml
PORT: 8080
RETAIL_UI_THEME: default | green | orange
RETAIL_UI_ENDPOINTS_CATALOG: http://retail-store-catalog:80
RETAIL_UI_ENDPOINTS_CARTS: http://retail-store-cart-carts:80
RETAIL_UI_ENDPOINTS_ORDERS: http://retail-store-orders:80
RETAIL_UI_ENDPOINTS_CHECKOUT: http://retail-store-checkout:80
RETAIL_UI_CHAT_ENABLED: false
```

### Catalog Service Configuration
```yaml
PORT: 8080
RETAIL_CATALOG_PERSISTENCE_PROVIDER: in-memory | mysql
RETAIL_CATALOG_PERSISTENCE_ENDPOINT: <mysql-endpoint>
RETAIL_CATALOG_PERSISTENCE_DB_NAME: catalogdb
RETAIL_CATALOG_PERSISTENCE_USER: catalog_user
RETAIL_CATALOG_PERSISTENCE_PASSWORD: <password>
```

### Cart Service Configuration
```yaml
PORT: 8080
RETAIL_CART_PERSISTENCE_PROVIDER: in-memory | dynamodb
RETAIL_CART_PERSISTENCE_DYNAMODB_TABLE_NAME: Items
RETAIL_CART_PERSISTENCE_DYNAMODB_ENDPOINT: <dynamodb-endpoint>
RETAIL_CART_PERSISTENCE_DYNAMODB_CREATE_TABLE: false
```

### Checkout Service Configuration
```yaml
PORT: 8080
RETAIL_CHECKOUT_PERSISTENCE_PROVIDER: in-memory | redis
RETAIL_CHECKOUT_PERSISTENCE_REDIS_URL: <redis-url>
RETAIL_CHECKOUT_ENDPOINTS_ORDERS: <orders-endpoint>
```

### Orders Service Configuration
```yaml
PORT: 8080
RETAIL_CHECKOUT_PERSISTENCE_PROVIDER: in-memory | postgres
RETAIL_ORDERS_PERSISTENCE_POSTGRES_ENDPOINT: <postgres-endpoint>
RETAIL_ORDERS_MESSAGING_PROVIDER: in-memory | sqs | rabbitmq
RETAIL_ORDERS_MESSAGING_SQS_TOPIC: <topic-name>
```

---

## 🎨 Key Features

### 1. **Chaos Engineering**
All services include chaos engineering endpoints:
- `/chaos/status/{code}` - Return specific HTTP status codes
- `/chaos/latency/{delay}` - Add artificial latency
- `/chaos/health` - Fail health checks

### 2. **Observability**
- Prometheus metrics on all services
- Health check endpoints
- Structured logging
- Distributed tracing support (OpenTelemetry)

### 3. **High Availability**
- Multi-AZ deployment
- Horizontal Pod Autoscaling (HPA)
- Pod Disruption Budgets (PDB)
- Load balancing with NGINX

### 4. **Security**
- Non-root containers
- Read-only root filesystem
- Dropped capabilities
- Network policies
- Secrets management
- SSL/TLS with Let's Encrypt

### 5. **Scalability**
- Auto-scaling based on CPU/memory
- Stateless service design
- External data persistence
- Load balancing

---

## 🔍 Monitoring & Troubleshooting

### Common Commands

```bash
# Check cluster status
kubectl get nodes

# Check all pods
kubectl get pods -n retail-store

# Check specific service
kubectl get pods -n retail-store -l app=ui

# View logs
kubectl logs -n retail-store <pod-name>

# Check ingress
kubectl get ingress -n retail-store

# Check ArgoCD applications
kubectl get applications -n argocd

# Port-forward to service
kubectl port-forward -n retail-store svc/retail-store-ui 8080:80
```

### Common Issues

#### **Image Pull Errors**
- Verify correct branch (main vs gitops)
- Check ECR repository exists
- Verify AWS credentials
- Check GitHub Actions logs

#### **ArgoCD Sync Issues**
- Check application status in ArgoCD UI
- Verify Git repository access
- Check Helm chart syntax
- Review sync logs

#### **Ingress Not Working**
- Verify NGINX controller is running
- Check ingress resource configuration
- Verify DNS/Load balancer setup
- Check security groups

---

## 🧹 Cleanup

### Destroy Infrastructure
```bash
cd terraform/
terraform destroy --auto-approve
```

**Note**: Manually delete ECR repositories from AWS Console if using GitOps branch.

---

## 📚 Technology Stack Summary

| Component | Technology | Version |
|-----------|-----------|---------|
| **Container Orchestration** | Kubernetes (EKS) | 1.33 |
| **Infrastructure** | Terraform | 1.0+ |
| **GitOps** | ArgoCD | Latest |
| **Ingress** | NGINX Ingress Controller | Latest |
| **Certificates** | Cert Manager + Let's Encrypt | Latest |
| **UI Service** | Java + Spring Boot | Java 21 |
| **Catalog Service** | Go | Latest |
| **Cart Service** | Java + Spring Boot | Java 21 |
| **Checkout Service** | Node.js + NestJS | Node 16+ |
| **Orders Service** | Java + Spring Boot | Java 21 |
| **Databases** | MySQL, PostgreSQL, DynamoDB, Redis | Various |
| **Messaging** | RabbitMQ, Amazon SQS | Latest |
| **CI/CD** | GitHub Actions | N/A |
| **Container Registry** | Amazon ECR | N/A |

---

## 🎯 Use Cases & Learning Objectives

This project demonstrates:

1. **Microservices Architecture**: Building and deploying independent services
2. **Container Orchestration**: Managing containers with Kubernetes
3. **GitOps**: Declarative infrastructure and application deployment
4. **Infrastructure as Code**: Automating infrastructure with Terraform
5. **CI/CD Pipelines**: Automated testing and deployment
6. **Cloud-Native Patterns**: Service discovery, load balancing, auto-scaling
7. **Observability**: Monitoring, logging, and tracing
8. **Security Best Practices**: Container security, network policies, secrets management
9. **High Availability**: Multi-AZ deployment, auto-scaling, health checks
10. **Chaos Engineering**: Testing resilience and failure scenarios

---

## 📖 Additional Resources

- **Main README**: `README.md` - Quick start and basic setup
- **Branching Strategy**: `BRANCHING_STRATEGY.md` - Detailed GitOps workflow
- **Terraform README**: `terraform/README.md` - Infrastructure details
- **Service READMEs**: `src/*/README.md` - Individual service documentation

---

## 🤝 Contributing & Support

- **Repository**: https://github.com/umar-sk-07/AIOps-Observability-Amazon-Q-MCP-Terraform
- **Issues**: GitHub Issues
- **Discord**: TrainWithShubhamCommunity
- **License**: Apache 2.0

---

## 💡 Quick Reference for Claude AI

When working with this project:

1. **For infrastructure changes**: Focus on `terraform/` directory
2. **For application code**: Work in `src/<service>/` directories
3. **For deployment configs**: Modify `src/<service>/chart/values.yaml`
4. **For GitOps setup**: Check `argocd/` directory
5. **For CI/CD**: Look at `.github/workflows/` (gitops branch)
6. **For architecture questions**: Reference this document and `README.md`
7. **For branching strategy**: Consult `BRANCHING_STRATEGY.md`

### Key Concepts to Remember:
- **Main branch** = Simple deployment with public images
- **GitOps branch** = Production with automated CI/CD
- **EKS Auto Mode** = Simplified node management
- **ArgoCD** = Handles all Kubernetes deployments
- **Terraform** = Manages all AWS infrastructure
- **Each service** = Independent microservice with own Helm chart

---

**Last Updated**: May 8, 2026
**Project Version**: 1.2.2
**Kubernetes Version**: 1.33
**Terraform Version**: 1.0+
