#!/bin/bash
# deploy.sh: Package Lambdas (with dependencies) and deploy with Terraform.
# Usage examples:
#   ./deploy.sh --telegram-id 123456789
#   ./deploy.sh --destroy

set -e

# Initialize variables
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
            echo "Unknown parameter passed: $1"
            exit 1
            ;;
    esac
    shift
done

# If the --destroy flag was passed, destroy resources and exit.
if [ $DESTROY -eq 1 ]; then
    echo "Destroying resources with Terraform..."
    cd terraform
    TELEGRAM_ID=1
    terraform destroy -var "telegram_id=${TELEGRAM_ID}" -auto-approve
    cd ..
    echo "Resources destroyed."
    exit 0
fi



echo "Packaging Lambdas..."

# Remove any existing build directory, then re-create it as blank.
rm -rf build
mkdir -p build

# Function to package a lambda given its folder name.
package_lambda() {
    local lambda_folder=$1
    echo "Packaging ${lambda_folder} Lambda..."
    cd "lambdas/${lambda_folder}"
    
    # Remove previous package directory if it exists, then create a new one.
    rm -rf package
    mkdir package

    # Install dependencies into the package directory if requirements.txt exists.
    if [ -f requirements.txt ]; then
        pip install -r requirements.txt -t package
    fi

    # Copy all Python source files into the package directory.
    cp *.py package/

    # Change into the package directory and zip its contents (not the folder itself).
    cd package
    zip -r ../../../build/"${lambda_folder}.zip" .
    cd ../../../
}

# Package each lambda
# package_lambda "email_fetcher"
# package_lambda "email_classifier"

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
echo "Deployment complete."
