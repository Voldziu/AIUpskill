param(
    [string]$ResourceGroupName = "rg-RAG",
    [string]$SearchServiceName = "aisearchbrochures"
)

Write-Host "Deleting Azure AI Search service: $SearchServiceName"
Remove-AzSearchService -ResourceGroupName $ResourceGroupName -Name $SearchServiceName -Force
Write-Host "Search service deleted. Indexes are backed up in storage account."