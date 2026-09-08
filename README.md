# CloudMart — Highly Available Multi-AZ E-Commerce Application on AWS

CloudMart is a highly available three-tier e-commerce application built on AWS to demonstrate production-style cloud architecture, fault tolerance, scalability, secure authentication, asynchronous order processing, and Multi-AZ deployment.

The application provides a public product storefront, authenticated checkout, order tracking, and an administrator workflow for approving or rejecting customer orders.

---

## Architecture

![CloudMart AWS Architecture](screenshots/architecture-diagram.png)

### High-Level Architecture

```text
                         Internet
                            │
                            ▼
                 Application Load Balancer
                     Public Subnets
                    AZ-A         AZ-B
                         │
                         ▼
                  Auto Scaling Group
                    /           \
                   ▼             ▼
               EC2 AZ-A       EC2 AZ-B
               Flask +        Flask +
               Gunicorn       Gunicorn
                   │             │
                   └──────┬──────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
     Aurora MySQL      Amazon S3       Amazon SQS
       Multi-AZ       Product Images    Order Queue
          │
     Writer + Reader

                         +
                   Amazon Cognito
                  User Authentication
                   Users / Admins
```

The VPC spans two Availability Zones and separates public, private application, and private database tiers.

---

## Project Overview

CloudMart demonstrates a complete AWS-hosted e-commerce workflow with:

- Public storefront accessible without authentication
- Shopping cart and authenticated checkout
- Amazon Cognito user authentication
- Email confirmation and login
- Role-based access for customers and administrators
- Highly available EC2 application tier
- Application Load Balancer
- Auto Scaling Group
- Multi-AZ Aurora MySQL database
- Amazon S3 product image storage
- Amazon SQS asynchronous order processing
- Background SQS worker
- Admin order approval and rejection
- Customer order status tracking
- IAM-based AWS service access
- AWS Systems Manager Parameter Store for Cognito configuration
- Linux systemd services for the web application and worker

---

## AWS Services Used

| AWS Service | Purpose |
|---|---|
| Amazon VPC | Isolated network spanning two Availability Zones |
| Application Load Balancer | Public entry point and traffic distribution |
| EC2 Auto Scaling | Maintains highly available application instances |
| Amazon EC2 | Runs Flask/Gunicorn application and SQS worker |
| Amazon Aurora MySQL | Multi-AZ persistent relational database |
| Amazon S3 | Stores product images and deployment artifacts |
| Amazon SQS | Decouples checkout from order processing |
| Amazon Cognito | User authentication and role management |
| AWS IAM | Controls access between AWS resources |
| AWS Systems Manager Parameter Store | Stores Cognito configuration securely |
| Amazon CloudWatch | Metrics and operational monitoring |
| NAT Gateway | Outbound connectivity for private instances |

**Region:** `ap-south-2` — Asia Pacific (Hyderabad)

---

# Multi-AZ High Availability

CloudMart runs inside a dedicated VPC spanning **two Availability Zones**.

The network contains six subnets:

```text
VPC
│
├── Availability Zone A
│   ├── Public Subnet
│   ├── Private Application Subnet
│   └── Private Database Subnet
│
└── Availability Zone B
    ├── Public Subnet
    ├── Private Application Subnet
    └── Private Database Subnet
```

This architecture prevents the application from depending on a single Availability Zone.

---

## Application Load Balancer

The internet-facing Application Load Balancer acts as the single public entry point.

```text
User
 │
 ▼
Application Load Balancer
 │
 ├────► EC2 Instance — AZ-A
 │
 └────► EC2 Instance — AZ-B
```

The ALB forwards requests only to healthy instances registered with its target group.

The Flask application exposes a `/healthz` endpoint that returns an HTTP `200` response for health checking.

![Application Load Balancer](screenshots/application-load-balancer.png)

---

## Auto Scaling Group

The application tier runs using an EC2 Auto Scaling Group across two Availability Zones.

The project maintains two healthy application instances and can automatically replace an unhealthy instance.

![Auto Scaling Group](screenshots/auto-scaling-group.png)

### Target Group Health

Both EC2 instances were verified as healthy and eligible to receive traffic from the load balancer.

![Target Group Health](screenshots/target-group-health.png)

---

## VPC & Subnets

The network uses six subnets across two Availability Zones, providing separate networking for the public, application, and database tiers.

![VPC and Subnets](screenshots/vpc-subnets.png)

---

## Amazon Aurora MySQL — Multi-AZ

Application data is stored in an Amazon Aurora MySQL cluster.

The database tier includes:

- Aurora writer instance
- Aurora reader instance
- Multi-AZ deployment
- Private database networking

The application tier connects privately to Aurora for product, order, and order-item data.

The Flask application uses PyMySQL for database connectivity.

![Aurora Multi-AZ](screenshots/aurora-multiaz.png)

---

## Amazon S3

Amazon S3 is used for:

1. Product image storage
2. Application deployment artifacts under `deploy/app/`

The media bucket remains private.

Instead of exposing product objects publicly, the application generates temporary S3 presigned URLs for displaying product images.

```text
Private S3 Object
       │
       ▼
Flask Application
       │
       ▼
Presigned URL
       │
       ▼
Customer Browser
```

![Amazon S3](screenshots/s3-bucket.png)

---

## Asynchronous Order Processing with Amazon SQS

Amazon SQS decouples customer checkout from backend order processing.

```text
Customer Checkout
       │
       ▼
     Aurora
Create PENDING Order
       │
       ▼
   Amazon SQS
       │
       ▼
Background Worker
       │
       ▼
Order → PROCESSING
       │
       ▼
Admin Approve / Reject
       │
       ▼
Customer Order Status
```

When checkout completes, the application stores the order in Aurora and publishes an order message to Amazon SQS.

A separate background worker long-polls the queue and handles the message asynchronously.

This allows the customer-facing checkout flow to remain decoupled from background processing.

![Amazon SQS](screenshots/sqs-queue.png)

### SQS Monitoring

CloudWatch metrics were used to verify that the queue was receiving and delivering messages.

![SQS CloudWatch Metrics](screenshots/sqs-cloudwatch-metrics.png)

---

## Amazon Cognito Authentication

Amazon Cognito handles:

- User sign-up
- Email confirmation
- Login
- Authentication
- ID token generation
- Role-based administrator access

The application verifies Cognito ID tokens before establishing the authenticated application session.

![Cognito User Pool](screenshots/cognito-user-pool.png)

### Admin Role

Administrators are identified through membership in the Cognito `Admins` group.

This allows the application to distinguish between:

```text
Guest
  │
  ├── Browse Products
  └── Use Shopping Cart

User
  │
  ├── Checkout
  └── View Orders

Admin
  │
  ├── View Orders
  ├── Approve Orders
  └── Reject Orders
```

![Cognito Admin Group](screenshots/cognito-admin-group.png)

---

## AWS Systems Manager Parameter Store

Cognito configuration is retrieved by the application from AWS Systems Manager Parameter Store.

The application expects the following parameters:

```text
/ecommerce/COGNITO_USER_POOL_ID
/ecommerce/COGNITO_CLIENT_ID
/ecommerce/COGNITO_CLIENT_SECRET
```

The Cognito client secret is requested with decryption enabled rather than being hardcoded into the application source.

Runtime database credentials and Flask secrets are also kept outside the GitHub source code.

---

# Application Workflow

## 1. Public Storefront

Guests can browse the product catalog without creating an account.

Product information is retrieved from Aurora MySQL, while private product images are displayed using temporary Amazon S3 presigned URLs.

![CloudMart Storefront](screenshots/storefront.png)

---

## 2. Shopping Cart

Customers can add products to their cart and modify quantities before authentication.

Cart data is maintained using the application's signed Flask session.

---

## 3. Authentication

Authentication is required when the customer proceeds to checkout.

Amazon Cognito handles:

```text
Sign Up
   │
   ▼
Email Confirmation
   │
   ▼
Login
   │
   ▼
Token Verification
   │
   ▼
Authenticated Session
```

---

## 4. Checkout

After authentication, the customer enters shipping information and places the order.

![CloudMart Checkout](screenshots/checkout.png)

---

## 5. Order Processing

When an order is placed:

```text
Checkout
   │
   ├──► Aurora → PENDING Order
   │
   └──► Amazon SQS → Order Message
                         │
                         ▼
                  Background Worker
                         │
                         ▼
                     PROCESSING
```

The SQS worker long-polls the queue, processes the order message, changes the order status to `PROCESSING`, and removes the successfully processed message from the queue.

---

## 6. Admin Dashboard

Administrators can view customer orders through the protected admin dashboard.

Orders in `PENDING` or `PROCESSING` state can be approved or rejected.

![Admin Dashboard](screenshots/admin-dashboard.png)

When approved, the order is marked `SHIPPED`.

When rejected, the order is marked `REJECTED`.

The updated status becomes visible to the customer through **My Orders**.

---

# Application Source Code

The repository contains the Flask application source used by CloudMart.

The application implements:

- Flask web application
- Product catalog
- Shopping cart
- Authenticated checkout
- Amazon Cognito authentication
- Cognito ID token verification
- Cognito administrator group authorization
- Aurora MySQL database access
- Amazon S3 presigned product image URLs
- Amazon SQS order publishing
- Background SQS worker
- Customer order history
- Administrator order management
- Application health endpoint

### Main Application Components

```text
app.py
        Main Flask application and routes

auth_utils.py
        Amazon Cognito authentication and token verification

config.py
        Environment and SSM-based application configuration

db.py
        Aurora MySQL database operations

s3_utils.py
        S3 presigned URL and object operations

sqs_utils.py
        Publishes order messages to Amazon SQS

worker.py
        Long-polls SQS and processes orders

templates/
        Flask/Jinja HTML templates

static/
        Application CSS
```

---

# Application Services

The application runs two independent Linux `systemd` services.

### Flask Web Application

```text
ecommerce.service
```

Runs the Flask application using Gunicorn.

### Background SQS Worker

```text
ecommerce-worker.service
```

Runs the independent Python SQS worker responsible for asynchronous order processing.

Both service definitions are included under:

```text
systemd/
```

Both services were verified as active and running during deployment.

![Application Service Health](screenshots/service-health.png)

---

# Security Practices

The project applies several AWS security practices:

- Application instances run in private subnets.
- Aurora database instances run in private database subnets.
- Only the Application Load Balancer is internet-facing.
- Private instances use a NAT Gateway for required outbound connectivity.
- Amazon Cognito handles user passwords and authentication.
- Cognito groups provide server-side role-based access.
- Cognito ID tokens are cryptographically verified by the application.
- S3 Block Public Access keeps the media bucket private.
- Product images are accessed using short-lived presigned URLs.
- EC2 uses an IAM role to access required AWS services.
- Database credentials and application secrets are kept outside source control.
- Cognito configuration is retrieved from SSM Parameter Store.
- Sensitive values are excluded using `.gitignore`.
- `.env.example` documents required configuration without exposing credentials.

> **Security Note:** Real environment files, database passwords, Flask secret keys, AWS credentials, and Cognito client secrets are intentionally excluded from this repository.

---

# Request & Order Flow

```text
                         USER
                           │
                           ▼
                 Application Load Balancer
                           │
                    ┌──────┴──────┐
                    ▼             ▼
                  EC2           EC2
                  AZ-A          AZ-B
                    │             │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
       Aurora              S3              SQS
       MySQL          Product Images       Queue
          │                                  │
          │                                  ▼
          │                          Background Worker
          │                                  │
          └────────────────┬─────────────────┘
                           ▼
                      Order Status
                           │
                           ▼
                      Admin Action
                           │
                           ▼
                   Customer My Orders
```

---

# Project Structure

```text
aws-cloudmart-multiaz-ecommerce/
│
├── app/
│   ├── app.py
│   ├── auth_utils.py
│   ├── config.py
│   ├── db.py
│   ├── s3_utils.py
│   ├── sqs_utils.py
│   ├── worker.py
│   ├── requirements.txt
│   │
│   ├── templates/
│   │   ├── 404.html
│   │   ├── admin_orders.html
│   │   ├── base.html
│   │   ├── cart.html
│   │   ├── checkout.html
│   │   ├── confirm.html
│   │   ├── index.html
│   │   ├── login.html
│   │   ├── my_orders.html
│   │   ├── order_success.html
│   │   ├── product.html
│   │   └── signup.html
│   │
│   └── static/
│       └── style.css
│
├── systemd/
│   ├── ecommerce.service
│   └── ecommerce-worker.service
│
├── screenshots/
│   ├── architecture-diagram.png
│   ├── vpc-subnets.png
│   ├── auto-scaling-group.png
│   ├── target-group-health.png
│   ├── application-load-balancer.png
│   ├── aurora-multiaz.png
│   ├── s3-bucket.png
│   ├── sqs-queue.png
│   ├── sqs-cloudwatch-metrics.png
│   ├── cognito-user-pool.png
│   ├── cognito-admin-group.png
│   ├── storefront.png
│   ├── checkout.png
│   ├── admin-dashboard.png
│   └── service-health.png
│
├── doc/
│   └── CloudMart AWS Project Documentation.pdf
│
├── .env.example
├── .gitignore
├── SOURCE_README.md
└── README.md
```

---

# Configuration

The real runtime environment file is intentionally excluded from this repository.

A safe example is provided:

```text
.env.example
```

It documents configuration for:

```text
DB_HOST
DB_USER
DB_PASSWORD
DB_NAME
DB_PORT
S3_BUCKET
AWS_REGION
SQS_QUEUE_URL
SECRET_KEY
```

Cognito configuration is retrieved separately from AWS Systems Manager Parameter Store.

**Never commit the real `env` or `.env` file to source control.**

---

# Project Documentation

The complete project documentation is available here:

[`CloudMart AWS Project Documentation.pdf`](doc/CloudMart%20AWS%20Project%20Documentation.pdf)

---

# What I Learned

This project provided hands-on experience with:

- Designing a three-tier AWS architecture
- Building Multi-AZ architectures
- Public and private subnet design
- Application Load Balancing
- EC2 Auto Scaling
- Target group health checks
- Amazon Aurora MySQL
- Python database connectivity with PyMySQL
- Amazon S3 private object access
- S3 presigned URLs
- Asynchronous processing with Amazon SQS
- SQS long polling
- Amazon Cognito authentication
- Cognito ID token verification
- Role-based access using Cognito groups
- AWS Systems Manager Parameter Store
- IAM instance roles
- Linux systemd services
- Gunicorn application deployment
- Application health verification
- Separating application configuration from source code
- Designing for high availability and fault tolerance

---

# Key AWS Concepts Demonstrated

`AWS` • `Multi-AZ` • `High Availability` • `Amazon VPC` • `ALB` • `EC2` • `Auto Scaling` • `Aurora MySQL` • `Amazon S3` • `Amazon SQS` • `Amazon Cognito` • `IAM` • `SSM Parameter Store` • `CloudWatch` • `NAT Gateway` • `Private Subnets` • `Presigned URLs` • `Three-Tier Architecture`

---

CloudMart was built as a hands-on AWS project to demonstrate how compute, networking, databases, storage, messaging, authentication, security, and application components can be combined into a highly available e-commerce architecture.
