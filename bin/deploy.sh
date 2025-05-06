#!/bin/bash
# deploy.sh: Package Lambdas (with dependencies) and deploy with Terraform.
# Usage:
#   ./deploy.sh --telegram-id 123456789
#   ./deploy.sh --destroy

set -e

DESTROY=0
TELEGRAM_ID=""

# Parse command-line arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --destroy)
            DESTROY=1
            ;;
        --telegram-id)
            if [ -n "$2" ]; then
                TELEGRAM_ID="$2"
                shift
            else
                echo "Error: --telegram-id requires a value"
                exit 1
            fi
            ;;
        *)
            echo "Unknown parameter: $1"
            exit 1
            ;;
    esac
    shift
done

# Destroy resources if flag is set
if [ $DESTROY -eq 1 ]; then
    echo "Destroying infrastructure..."
    cd terraform
    TELEGRAM_ID=1
    terraform destroy -var "telegram_id=${TELEGRAM_ID}" -auto-approve
    cd ..
    echo "Destroyed."
    exit 0
fi

echo "Packaging Lambdas..."

rm -rf build
mkdir -p build

# Docker-based packaging
package_lambda() {
    local lambda_folder=$1
    local lambda_name="${lambda_folder##*/}"

    echo "Packaging $lambda_name..."

    # Copy the lambda's requirements.txt into bin/ as temp input for Dockerfile
    cp "${lambda_folder}/requirements.txt" bin/requirements.txt

    # Build the image using bin/ as context
    docker build \
        -t "lambda-package-${lambda_name}" \
        -f bin/Dockerfile \
        bin

    # Run the built image to zip the contents
    docker run --rm \
        -v "$(pwd)/build":/build \
        -v "$(realpath ${lambda_folder})":/src \
        -w /app/package \
        "lambda-package-${lambda_name}" \
        bash -c "cp /src/*.py . && zip -r /build/${lambda_name}.zip . > /dev/null"

    # Clean up temp copied requirements.txt
    rm bin/requirements.txt

    echo "✓ Done: build/${lambda_name}.zip"
}

# Add more lambdas here as needed
package_lambda "src/lambda/sanitizer"

echo "Deploying with Terraform..."

cd terraform
terraform init

if [ -n "$TELEGRAM_ID" ]; then
    terraform plan -var "telegram_id=${TELEGRAM_ID}" -out=tfplan.out
    terraform apply -auto-approve tfplan.out
else
    terraform plan -out=tfplan.out
    terraform apply -auto-approve tfplan.out
fi

rm tfplan.out
cd ..
echo "✅ Deployment complete."
