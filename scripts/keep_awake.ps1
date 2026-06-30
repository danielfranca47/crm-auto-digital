<#
Mantem o Windows acordado (sem suspender) enquanto este script estiver
rodando. Nao altera nenhuma configuracao global de energia -- ao fechar
esta janela (Ctrl+C ou X), o comportamento normal de suspensao volta.

Uso: abrir um terminal dedicado so para isto e deixar rodando durante
toda a sessao de teste remoto (junto com backend-core, backend-crm,
dev_proxy.py e ngrok).
#>

Add-Type -Name Power -Namespace Win32 -MemberDefinition @'
[DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
public static extern uint SetThreadExecutionState(uint esFlags);
'@

$ES_CONTINUOUS       = [uint32]"0x80000000"
$ES_SYSTEM_REQUIRED  = [uint32]"0x00000001"
$ES_DISPLAY_REQUIRED = [uint32]"0x00000002"

Write-Output "Mantendo o Windows acordado. Pressione Ctrl+C para parar e devolver o comportamento normal de suspensao."

try {
    while ($true) {
        [Win32.Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED -bor $ES_DISPLAY_REQUIRED) | Out-Null
        Start-Sleep -Seconds 30
    }
} finally {
    [Win32.Power]::SetThreadExecutionState($ES_CONTINUOUS) | Out-Null
    Write-Output "Suspensao normal restaurada."
}
