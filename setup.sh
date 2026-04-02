#!/bin/bash
# =============================================================================
# Cloud Compiler Platform — Azure Resource Setup Script
# Run this once to provision all required Azure resources.
# Prerequisites: Azure CLI installed and logged in (az login)
# =============================================================================

set -e  # Exit immediately on any error

# ---------- CONFIGURATION — edit these before running ----------
RESOURCE_GROUP="cloud-compiler-rg"
LOCATION="UAENorth"
STORAGE_ACCOUNT="cloudcompilerstorage"
FUNC_STORAGE="compilerafuncstorage"
ACR_NAME="cloudcompileracr"
AI_SERVICE_NAME="cloud-compiler-ai"
INSIGHTS_NAME="cloud-compiler-insights"
FUNC_APP_NAME="cloud-compiler-func"
CONTAINER_ENV="compiler-env"
CONTAINER_APP="llvm-compiler-app"
SWA_NAME="cloud-compiler-swa"
SWA_LOCATION="eastasia"
# ---------------------------------------------------------------

echo ""
echo "======================================================"
echo "  Cloud Compiler Platform — Azure Resource Setup"
echo "======================================================"
echo ""

# 1. Resource Group
echo "[1/9] Creating Resource Group: $RESOURCE_GROUP..."
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none
echo "      ✅ Done"

# 2. Blob Storage Account + Containers + Tables
echo "[2/9] Creating Storage Account: $STORAGE_ACCOUNT..."
az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --output none

CONN_STR=$(az storage account show-connection-string \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --output tsv)

echo "      Creating Blob containers..."
az storage container create --name code-uploads      --connection-string "$CONN_STR" --output none
az storage container create --name compiled-outputs  --connection-string "$CONN_STR" --output none
az storage container create --name compile-logs      --connection-string "$CONN_STR" --output none

echo "      Creating Table Storage tables..."
az storage table create --name CompilationHistory --connection-string "$CONN_STR" --output none
az storage table create --name ErrorTypes         --connection-string "$CONN_STR" --output none
echo "      ✅ Done"

# 3. Container Registry
echo "[3/9] Creating Container Registry: $ACR_NAME..."
az acr create \
  --name "$ACR_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --sku Basic \
  --admin-enabled true \
  --output none
echo "      ✅ Done"

# 4. Azure AI Language Service
echo "[4/9] Creating AI Language Service: $AI_SERVICE_NAME..."
az cognitiveservices account create \
  --name "$AI_SERVICE_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --kind TextAnalytics \
  --sku F0 \
  --location "$LOCATION" \
  --yes \
  --output none
echo "      ✅ Done"

# 5. Application Insights
echo "[5/9] Creating Application Insights: $INSIGHTS_NAME..."
az monitor app-insights component create \
  --app "$INSIGHTS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --kind web \
  --output none
echo "      ✅ Done"

# 6. Function App Storage + Function App
echo "[6/9] Creating Function App: $FUNC_APP_NAME..."
az storage account create \
  --name "$FUNC_STORAGE" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --output none

az functionapp create \
  --name "$FUNC_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --storage-account "$FUNC_STORAGE" \
  --runtime python \
  --runtime-version 3.10 \
  --functions-version 4 \
  --os-type linux \
  --consumption-plan-location "$LOCATION" \
  --output none
echo "      ✅ Done"

# 7. Container Apps Environment (no container deployed yet — push image first)
echo "[7/9] Creating Container Apps Environment: $CONTAINER_ENV..."
az containerapp env create \
  --name "$CONTAINER_ENV" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --output none
echo "      ✅ Done"

# 8. Static Web App
echo "[8/9] Creating Static Web App: $SWA_NAME..."
az staticwebapp create \
  --name "$SWA_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "$SWA_LOCATION" \
  --sku Free \
  --output none
echo "      ✅ Done"

# 9. Configure Function App settings
echo "[9/9] Configuring Function App environment variables..."

AI_ENDPOINT=$(az cognitiveservices account show \
  --name "$AI_SERVICE_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query properties.endpoint \
  --output tsv)

AI_KEY=$(az cognitiveservices account keys list \
  --name "$AI_SERVICE_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query key1 \
  --output tsv)

INSIGHTS_KEY=$(az monitor app-insights component show \
  --app "$INSIGHTS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query instrumentationKey \
  --output tsv)

az functionapp config appsettings set \
  --name "$FUNC_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --settings \
    "AZURE_STORAGE_CONNECTION_STRING=$CONN_STR" \
    "AI_LANGUAGE_ENDPOINT=$AI_ENDPOINT" \
    "AI_LANGUAGE_KEY=$AI_KEY" \
    "APPINSIGHTS_INSTRUMENTATIONKEY=$INSIGHTS_KEY" \
    "CONTAINER_APP_URL=PLACEHOLDER_UPDATE_AFTER_DOCKER_DEPLOY" \
  --output none

az functionapp cors add \
  --name "$FUNC_APP_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --allowed-origins '*' \
  --output none

echo "      ✅ Done"

# ---- Summary ----
echo ""
echo "======================================================"
echo "  ✅ All resources created successfully!"
echo "======================================================"
echo ""
echo "  Resource Group  : $RESOURCE_GROUP"
echo "  Storage Account : $STORAGE_ACCOUNT"
echo "  Container Reg.  : $ACR_NAME"
echo "  AI Endpoint     : $AI_ENDPOINT"
echo "  Function App    : https://$FUNC_APP_NAME.azurewebsites.net/api"
echo ""
echo "  STORAGE CONNECTION STRING (save this):"
echo "  $CONN_STR"
echo ""
echo "------------------------------------------------------"
echo "  NEXT STEPS:"
echo "  1. Build & push Docker image:"
echo "     cd docker"
echo "     docker build -t cloud-compiler-llvm:latest ."
echo "     az acr login --name $ACR_NAME"
echo "     docker tag cloud-compiler-llvm:latest $ACR_NAME.azurecr.io/cloud-compiler-llvm:latest"
echo "     docker push $ACR_NAME.azurecr.io/cloud-compiler-llvm:latest"
echo ""
echo "  2. Deploy Container App and get its FQDN, then update"
echo "     CONTAINER_APP_URL in the Function App settings."
echo ""
echo "  3. Deploy Functions:  func azure functionapp publish $FUNC_APP_NAME"
echo ""
echo "  4. Deploy frontend:   swa deploy ./frontend --deployment-token <TOKEN>"
echo "======================================================"
