# create-search-service.ps1 - Deploy Azure AI Search
param(
    [string]$ResourceGroupName = "rg-RAG",
    [string]$Location = "Central US",
    [string]$TemplateFile = "deploy.bicep"
)

# Deploy Bicep template
$deployment = New-AzResourceGroupDeployment `
    -ResourceGroupName $ResourceGroupName `
    -TemplateFile $TemplateFile `
    -Verbose

Write-Host "Search service created: $($deployment.Outputs.searchServiceName.Value)"
Write-Host "Endpoint: $($deployment.Outputs.searchServiceEndpoint.Value)"

# Get admin key and display for .env
$adminKey = (Get-AzSearchAdminKeyPair -ResourceGroupName $ResourceGroupName -ServiceName $deployment.Outputs.searchServiceName.Value).Primary
Write-Host ""
Write-Host "PRZEKLEJ DO .ENV:" -ForegroundColor Yellow
Write-Host "AZURE_SEARCH_ENDPOINT = $($deployment.Outputs.searchServiceEndpoint.Value)" -ForegroundColor Green
Write-Host "AZURE_SEARCH_KEY = $adminKey" -ForegroundColor Green