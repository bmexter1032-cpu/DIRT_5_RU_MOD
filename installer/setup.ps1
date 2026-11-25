param([Parameter(Mandatory=$true)][ValidateSet('install','uninstall')][string]$Mode)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
$installing = $Mode -eq 'install'
$title = 'DIRT 5 — Русификатор'
$verb = if ($installing) { 'Установить' } else { 'Удалить' }
$python = Join-Path $PSScriptRoot 'runtime\python.exe'
$driver = Join-Path $PSScriptRoot 'patcher\easy_driver.py'
function Show-Message([string]$Text, [string]$Kind = 'Information') {
    $ic = [System.Windows.Forms.MessageBoxIcon]$Kind
    [void][System.Windows.Forms.MessageBox]::Show($Text,$title,[System.Windows.Forms.MessageBoxButtons]::OK,$ic)
}
if (!(Test-Path -LiteralPath $python -PathType Leaf) -or !(Test-Path -LiteralPath $driver -PathType Leaf)) {
    Show-Message 'Распакуйте весь архив русификатора. Служебные файлы не найдены.' 'Error'; exit 1
}
$logDir = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'DIRT_5_RU_MOD'
try { [void](New-Item -ItemType Directory -Force -Path $logDir) } catch { Show-Message "Не удалось создать папку журнала: $($_.Exception.Message)" 'Error'; exit 1 }
$stateFile = Join-Path $logDir 'last_game.txt'
$script:busy = $false
$script:result = 0
$script:gameState = 'UNKNOWN'
$form = New-Object Windows.Forms.Form
$form.Text = $title
$form.StartPosition = 'CenterScreen'
$form.ClientSize = New-Object Drawing.Size(620,275)
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.Font = New-Object Drawing.Font('Segoe UI',10)
$form.AutoScaleMode = 'Dpi'
$heading = New-Object Windows.Forms.Label
$heading.Text = if ($installing) { 'Установка русской локализации' } else { 'Удаление русской локализации' }
$heading.Font = New-Object Drawing.Font('Segoe UI',15,[Drawing.FontStyle]::Bold)
$heading.SetBounds(20,15,580,34)
$sub = New-Object Windows.Forms.Label
$sub.Text = 'Русский текст · Оригинальная английская озвучка'
$sub.SetBounds(22,52,575,26)
$label = New-Object Windows.Forms.Label
$label.Text = 'Папка с установленной DIRT 5:'
$label.SetBounds(22,89,575,25)
$pathBox = New-Object Windows.Forms.TextBox
$pathBox.SetBounds(22,116,465,28)
$browse = New-Object Windows.Forms.Button
$browse.Text = 'Обзор…'; $browse.SetBounds(495,114,103,31)
$action = New-Object Windows.Forms.Button
$action.Text = $verb; $action.SetBounds(22,169,178,36)
$action.Enabled = $false
$repair = New-Object Windows.Forms.Button
$repair.Text = 'Создать ярлык'; $repair.SetBounds(214,169,198,36)
$repair.Visible = $false; $repair.Enabled = $false
$cancel = New-Object Windows.Forms.Button
$cancel.Text = 'Закрыть'; $cancel.SetBounds(438,169,160,36)
$status = New-Object Windows.Forms.Label
$status.Text = 'Выберите папку игры. Резервная копия создаётся автоматически.'
if (!$installing) { $status.Text = 'Будут восстановлены оригинальные игровые файлы.' }
$status.SetBounds(22,216,580,50)
$form.Controls.AddRange(@($heading,$sub,$label,$pathBox,$browse,$action,$repair,$cancel,$status))
$form.AcceptButton = $action
$form.CancelButton = $cancel
try { if (Test-Path -LiteralPath $stateFile) { $last = [IO.File]::ReadAllText($stateFile).Trim(); if (Test-Path -LiteralPath $last -PathType Container) { $pathBox.Text = $last } } } catch {}
if (!$pathBox.Text) {
    $candidate = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    if (Test-Path -LiteralPath (Join-Path $candidate 'game_release.exe')) { $pathBox.Text = $candidate }
}
$browse.Add_Click({
    $dialog = New-Object Windows.Forms.FolderBrowserDialog
    try {
        $dialog.Description = 'Выберите папку, в которой находится game_release.exe'
        $dialog.ShowNewFolderButton = $false
        if ($pathBox.Text -and (Test-Path -LiteralPath $pathBox.Text -PathType Container)) { $dialog.SelectedPath = $pathBox.Text }
        if ($dialog.ShowDialog($form) -eq [Windows.Forms.DialogResult]::OK) { $pathBox.Text = $dialog.SelectedPath }
    } finally { $dialog.Dispose() }
})
$cancel.Add_Click({ if (!$script:busy) { $form.Close() } })
$form.Add_FormClosing({ param($sender,$e) if ($script:busy) { $e.Cancel = $true } })
function Update-Shortcut([string]$Game, [bool]$Create) {
    $desktop = [Environment]::GetFolderPath('DesktopDirectory')
    if ([string]::IsNullOrWhiteSpace($desktop)) { throw 'Папка рабочего стола недоступна.' }
    $target = Join-Path $Game 'game_release.exe'
    $primary = Join-Path $desktop 'DIRT 5 — Русская версия.lnk'
    $legacy = Join-Path $desktop 'DIRT 5 - RU.lnk'
    $shell = New-Object -ComObject WScript.Shell
    try {
        if ($Create) {
            $link = $shell.CreateShortcut($primary)
            if ((Test-Path -LiteralPath $primary) -and ($link.TargetPath -ne $target -or $link.Arguments -ne '-language rus')) { throw 'Ярлык с таким именем уже существует и относится к другой игре.' }
            $link.TargetPath = $target; $link.Arguments = '-language rus'; $link.WorkingDirectory = $Game; $link.IconLocation = "$target,0"; $link.Description = 'DIRT 5 — русский текст, английская озвучка'; $link.Save()
        } else {
            foreach ($name in @($primary,$legacy)) {
                if (Test-Path -LiteralPath $name) {
                    $link = $shell.CreateShortcut($name)
                    if ($link.TargetPath -eq $target -and $link.Arguments -eq '-language rus') { Remove-Item -LiteralPath $name -ErrorAction Stop }
                }
            }
        }
    } finally { if ($null -ne $shell) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($shell) } }
}
# Share the existing UTF-8, no-console process runner for status and writes.
function Invoke-Driver([string]$Operation,[string]$Game) {
    $psi = New-Object Diagnostics.ProcessStartInfo
    $psi.FileName = $python
    $psi.Arguments = '-B "' + $driver + '"'
    $psi.WorkingDirectory = $PSScriptRoot
    $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [Text.Encoding]::UTF8; $psi.StandardErrorEncoding = [Text.Encoding]::UTF8
    $psi.EnvironmentVariables['DIRT_RU_ACTION'] = $Operation; $psi.EnvironmentVariables['DIRT_RU_GAME'] = $Game
    $proc = New-Object Diagnostics.Process; $proc.StartInfo = $psi
    try {
        [void]$proc.Start()
        $out = $proc.StandardOutput.ReadToEndAsync(); $err = $proc.StandardError.ReadToEndAsync()
        while (!$proc.WaitForExit(150)) { [Windows.Forms.Application]::DoEvents() }
        $proc.WaitForExit()
        return @{ Text = ($out.GetAwaiter().GetResult() + "`r`n" + $err.GetAwaiter().GetResult()); Code = $proc.ExitCode }
    } finally { $proc.Dispose() }
}
function Set-State([string]$State) {
    $script:gameState = $State
    $action.Enabled = $false; $action.Text = $verb
    $repair.Visible = $false; $repair.Enabled = $false
    switch ($State) {
        'VANILLA' {
            if ($installing) { $status.Text = 'Русификатор не установлен. Можно установить.'; $action.Enabled = $true }
            else { $status.Text = 'Русификатор не установлен.'; $action.Text = 'Не установлен' }
        }
        'INSTALLED' {
            $status.Text = 'Русификатор уже установлен.'
            if ($installing) { $action.Text = 'Уже установлен'; $repair.Visible = $true; $repair.Enabled = $true }
            else { $action.Enabled = $true }
        }
        'RECOVERABLE' {
            $status.Text = 'Незавершённая установка. Восстановите оригинальные файлы через Uninstall_RU.bat.'
            if (!$installing) { $action.Text = 'Восстановить'; $action.Enabled = $true }
        }
        'INVALID' { $status.Text = 'Выберите папку с game_release.exe и dat.' }
        'BLOCKED' { $status.Text = 'Версия игры не поддерживается или файлы изменены. Операция недоступна.' }
        'ERROR' { $status.Text = 'Не удалось проверить файлы игры. Подробности в журнале.' }
        default { $status.Text = 'Проверка состояния игры…' }
    }
}
function Refresh-State {
    if ($script:busy) { return }
    $timer.Stop()
    $script:busy = $true
    $pathBox.Enabled = $false; $browse.Enabled = $false; $cancel.Enabled = $false
    $form.UseWaitCursor = $true
    try {
        Set-State 'UNKNOWN'
        $form.Refresh()
        $game = $pathBox.Text.Trim().Trim('"')
        if ([string]::IsNullOrWhiteSpace($game) -or !(Test-Path -LiteralPath (Join-Path $game 'game_release.exe') -PathType Leaf) -or !(Test-Path -LiteralPath (Join-Path $game 'dat\index\dat.ndx') -PathType Leaf)) { Set-State 'INVALID'; return }
        $result = Invoke-Driver 'status' $game
        if ($result.Code -eq 0 -and $result.Text -match '(?m)^STATE: (VANILLA|INSTALLED|RECOVERABLE|BLOCKED)\s*$') {
            Set-State $Matches[1]
        } else {
            $log = Join-Path $logDir 'status.log'
            [IO.File]::WriteAllText($log,$result.Text,[Text.Encoding]::UTF8)
            Set-State 'ERROR'
        }
    } catch { Set-State 'ERROR' }
    finally {
        $script:busy = $false; $form.UseWaitCursor = $false
        $pathBox.Enabled = $true; $browse.Enabled = $true; $cancel.Enabled = $true
    }
}
$timer = New-Object Windows.Forms.Timer
$timer.Interval = 450
$timer.Add_Tick({ $timer.Stop(); Refresh-State })
$pathBox.Add_TextChanged({ if (!$script:busy) { Set-State 'UNKNOWN'; $timer.Stop(); $timer.Start() } })
$form.Add_Shown({ Refresh-State })
$repair.Add_Click({
    if ($script:busy) { return }
    Refresh-State
    if ($script:gameState -ne 'INSTALLED') { return }
    try {
        $game = (Get-Item -LiteralPath $pathBox.Text.Trim().Trim('"')).FullName
        Update-Shortcut $game $true
        Show-Message 'Ярлык создан на рабочем столе.'
    } catch { Show-Message "Не удалось создать ярлык: $($_.Exception.Message)" 'Error' }
})
$action.Add_Click({
    if ($script:busy) { return }
    Refresh-State
    if (!$action.Enabled) { return }
    try {
        if ([string]::IsNullOrWhiteSpace($pathBox.Text)) { Show-Message 'Сначала выберите папку игры.' 'Warning'; return }
        $game = (Get-Item -LiteralPath $pathBox.Text.Trim().Trim('"') -ErrorAction Stop).FullName
        if (!(Test-Path -LiteralPath (Join-Path $game 'game_release.exe') -PathType Leaf) -or !(Test-Path -LiteralPath (Join-Path $game 'dat\index\dat.ndx') -PathType Leaf)) { Show-Message 'Выбрана неверная папка. Нужна папка с game_release.exe и dat.' 'Warning'; return }
        if (Get-Process -Name game_release -ErrorAction SilentlyContinue) { Show-Message 'Закройте DIRT 5 и повторите попытку.' 'Warning'; return }
        if (!$installing -and !(Test-Path -LiteralPath (Join-Path $game '_ru_tools\DIRT_RU_1_0_backup.zip') -PathType Leaf)) { Show-Message 'Резервная копия русификатора не найдена. Файлы игры не изменены.' 'Warning'; return }
        $script:busy = $true
        $action.Enabled = $false; $repair.Enabled = $false; $browse.Enabled = $false; $pathBox.Enabled = $false; $cancel.Enabled = $false
        $form.UseWaitCursor = $true
        $status.Text = 'Выполняется проверка и обработка файлов. Не закрывайте окно.'
        $form.Refresh()
        $log = Join-Path $logDir ((Get-Date -Format 'yyyyMMdd_HHmmss_ffff') + '_' + $Mode + '.log')
        $result = Invoke-Driver $Mode $game
        $text = $result.Text; $rc = $result.Code
        [IO.File]::WriteAllText($log, $text, [Text.Encoding]::UTF8)
        if ($rc -ne 0) {
            $reason = 'Операция не завершена. Не удаляйте резервную копию.'
            if ($text -match 'Unsupported or modified game|Unexpected DAT size|Original Xbox BRA|Original font|Foreign EXE/index|Release output') { $reason = 'Версия игры не поддерживается или её файлы изменены. Не обходите проверку совместимости.' }
            elseif ($text -match 'PermissionError|Access is denied') { $reason = 'Недостаточно прав на запись в папку игры.' }
            elseif ($text -match 'Close DIRT 5') { $reason = 'Закройте игру и повторите попытку.' }
            elseif ($text -match 'Incomplete or foreign installation') { $reason = 'Найдена незавершённая установка. Сначала выполните удаление.' }
            $status.Text = 'Операция не завершена.'; $script:result = 1
            Show-Message "$reason`r`n`r`nЖурнал: $log" 'Error'; return
        }
        $script:result = 0
        try { [IO.File]::WriteAllText($stateFile,$game,[Text.Encoding]::UTF8) } catch {}
        $notice = ''
        try { Update-Shortcut $game $installing } catch { $notice = "`r`n`r`nНе удалось обновить ярлык: $($_.Exception.Message)" }
        if ($installing) {
            $status.Text = 'Русификатор установлен.'
            $done = 'Русификатор установлен. Запускайте игру через ярлык «DIRT 5 — Русская версия».'
            if ($notice) { $done = 'Русификатор установлен. Для создания ярлыка используйте кнопку «Создать ярлык».' }
        } else { $status.Text = 'Оригинальные файлы восстановлены.'; $done = 'Русификатор удалён. Оригинальные файлы восстановлены.' }
        Show-Message ($done + $notice)
    } catch {
        $script:result = 1; $status.Text = 'Операция не завершена.'
        Show-Message "Ошибка: $($_.Exception.Message)" 'Error'
    } finally {
        $script:busy = $false; $form.UseWaitCursor = $false
        $browse.Enabled = $true; $pathBox.Enabled = $true; $cancel.Enabled = $true
        Refresh-State
    }
})
[void]$form.ShowDialog()
$timer.Stop(); $timer.Dispose()
$form.Dispose()
exit $script:result
