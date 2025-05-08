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

# Docker-based packaging
package_lambda() {
    local lambda_folder=$1
    local lambda_name="${lambda_folder##*/}"
    local zip_path="build/${lambda_name}.zip"
    local hash_file="${lambda_folder}/.last_build_hash"

    echo "Checking $lambda_name for changes..."

    # Compute hash of source files
    local current_hash
    current_hash=$(find "$lambda_folder" -type f \( -name "*.py" -o -name "requirements.txt" \) -exec sha256sum {} \; | sha256sum | awk '{print $1}')

    if [ -f "$hash_file" ] && [[ "$current_hash" == "$(cat "$hash_file")" ]]; then
        echo "⏩ No changes in $lambda_name, skipping packaging."
        return
    fi

    echo "📦 Packaging $lambda_name..."

    # Delete previous zip if rebuilding
    if [ -f "$zip_path" ]; then
        echo "🧹 Removing old zip: $zip_path"
        rm "$zip_path"
    fi

    # Copy requirements.txt into Docker context
    cp "${lambda_folder}/requirements.txt" bin/requirements.txt

    # Build Docker image
    docker build \
        -t "lambda-package-${lambda_name}" \
        -f bin/Dockerfile \
        bin

    # Run container to zip the Lambda
    docker run --rm \
        -v "$(pwd)/build":/build \
        -v "$(realpath ${lambda_folder})":/src \
        -w /app/package \
        "lambda-package-${lambda_name}" \
        bash -c "cp /src/*.py . && zip -r /build/${lambda_name}.zip . > /dev/null"

    # Save hash for future comparisons
    echo "$current_hash" > "$hash_file"

    # Clean up Docker context
    rm bin/requirements.txt

    echo "✅ Done: build/${lambda_name}.zip"
}


# Add more lambdas here as needed
package_lambda "src/lambda/sanitizer"
package_lambda "src/lambda/classifier"
package_lambda "src/lambda/notifier"

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
