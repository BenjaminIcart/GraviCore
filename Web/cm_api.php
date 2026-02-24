<?php
/**
 * Centre de Masse — Remote Monitoring API + Auto-Update
 *
 * Upload this file to: https://ibenji.fr/plancheadmin/cm_api.php
 *
 * STRUCTURE AUTO-CREEE:
 *   plancheadmin/
 *     cm_api.php          <-- ce fichier
 *     cm_data/             <-- heartbeats (auto)
 *     cm_updates/          <-- fichiers de mise a jour (auto)
 *       version.json       <-- {"version": 2}
 *       CentredeMasse.exe  <-- le .exe a distribuer
 */

define('API_KEY', 'c4d1146e19f391e0b6901bcb88c32d10e7f6e5174d12f179bd7a1018b4c9c8e0');
define('DATA_DIR', __DIR__ . '/cm_data');
define('UPDATE_DIR', __DIR__ . '/cm_updates');
define('MAX_EXE_SIZE', 200 * 1024 * 1024); // 200 MB max

// Create directories if needed
foreach ([DATA_DIR, UPDATE_DIR] as $dir) {
    if (!is_dir($dir)) {
        mkdir($dir, 0755, true);
        file_put_contents($dir . '/.htaccess', "Deny from all\n");
    }
}

$api_key_header = $_SERVER['HTTP_X_API_KEY'] ?? '';

// ── GET ?action=version — Return current version for auto-update ──
if ($_SERVER['REQUEST_METHOD'] === 'GET' && ($_GET['action'] ?? '') === 'version') {
    $ver_file = UPDATE_DIR . '/version.json';
    if (file_exists($ver_file)) {
        $ver = json_decode(file_get_contents($ver_file), true);
    } else {
        $ver = ['version' => 0];
    }
    // Build download URL (same base as this script)
    $proto = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
    $host = $_SERVER['HTTP_HOST'];
    $base = dirname($_SERVER['SCRIPT_NAME']);
    $ver['download_url'] = "$proto://$host$base/cm_api.php?action=download";
    header('Content-Type: application/json');
    echo json_encode($ver);
    exit;
}

// ── GET ?action=download — Serve the .exe file (API key required) ──
if ($_SERVER['REQUEST_METHOD'] === 'GET' && ($_GET['action'] ?? '') === 'download') {
    if ($api_key_header !== API_KEY) {
        http_response_code(403);
        echo 'Forbidden';
        exit;
    }
    $exe = UPDATE_DIR . '/CentredeMasse.exe';
    if (!file_exists($exe)) {
        http_response_code(404);
        echo 'No update file available';
        exit;
    }
    header('Content-Type: application/octet-stream');
    header('Content-Disposition: attachment; filename="CentredeMasse.exe"');
    header('Content-Length: ' . filesize($exe));
    readfile($exe);
    exit;
}

// ── GET ?action=public_download — Serve .exe without API key (for download page) ──
if ($_SERVER['REQUEST_METHOD'] === 'GET' && ($_GET['action'] ?? '') === 'public_download') {
    $exe = UPDATE_DIR . '/CentredeMasse.exe';
    if (!file_exists($exe)) {
        http_response_code(404);
        echo 'Aucun fichier disponible pour le moment.';
        exit;
    }
    // Track download count
    $dl_count_file = DATA_DIR . '/_download_count.txt';
    $count = file_exists($dl_count_file) ? intval(file_get_contents($dl_count_file)) : 0;
    file_put_contents($dl_count_file, $count + 1);

    header('Content-Type: application/octet-stream');
    header('Content-Disposition: attachment; filename="CentredeMasse.exe"');
    header('Content-Length: ' . filesize($exe));
    header('Cache-Control: no-cache');
    readfile($exe);
    exit;
}

// ── GET ?action=installer — Serve .bat installer script ──────
if ($_SERVER['REQUEST_METHOD'] === 'GET' && ($_GET['action'] ?? '') === 'installer') {
    $exe = UPDATE_DIR . '/CentredeMasse.exe';
    if (!file_exists($exe)) {
        http_response_code(404);
        echo 'Aucun fichier disponible pour le moment.';
        exit;
    }

    // Build the download URL for the .exe
    $proto = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
    $host  = $_SERVER['HTTP_HOST'];
    $base  = dirname($_SERVER['SCRIPT_NAME']);
    $exe_url = "$proto://$host$base/cm_api.php?action=public_download";

    // Track installer download count
    $dl_count_file = DATA_DIR . '/_installer_count.txt';
    $count = file_exists($dl_count_file) ? intval(file_get_contents($dl_count_file)) : 0;
    file_put_contents($dl_count_file, $count + 1);

    $bat = "@echo off\r\n";
    $bat .= "chcp 65001 >nul 2>&1\r\n";
    $bat .= "title Installation - Centre de Masse\r\n";
    $bat .= "color 0B\r\n";
    $bat .= "echo.\r\n";
    $bat .= "echo  ========================================\r\n";
    $bat .= "echo    Centre de Masse - Installation\r\n";
    $bat .= "echo  ========================================\r\n";
    $bat .= "echo.\r\n";
    $bat .= "\r\n";
    $bat .= "set \"INSTALL_DIR=%LOCALAPPDATA%\\Programs\\CentredeMasse\"\r\n";
    $bat .= "\r\n";
    $bat .= "echo  [1/4] Creation du dossier d'installation...\r\n";
    $bat .= "if not exist \"%INSTALL_DIR%\" mkdir \"%INSTALL_DIR%\"\r\n";
    $bat .= "echo         %INSTALL_DIR%\r\n";
    $bat .= "echo.\r\n";
    $bat .= "\r\n";
    $bat .= "echo  [2/4] Telechargement de l'application...\r\n";
    $bat .= "echo         Cela peut prendre quelques minutes...\r\n";
    $bat .= "powershell -Command \"[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; \$ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri '$exe_url' -OutFile '%INSTALL_DIR%\\CentredeMasse.exe'\"\r\n";
    $bat .= "if not exist \"%INSTALL_DIR%\\CentredeMasse.exe\" (\r\n";
    $bat .= "    echo.\r\n";
    $bat .= "    color 0C\r\n";
    $bat .= "    echo  ERREUR: Le telechargement a echoue.\r\n";
    $bat .= "    echo  Verifiez votre connexion internet et reessayez.\r\n";
    $bat .= "    echo.\r\n";
    $bat .= "    pause\r\n";
    $bat .= "    exit /b 1\r\n";
    $bat .= ")\r\n";
    $bat .= "echo         Telechargement termine !\r\n";
    $bat .= "echo.\r\n";
    $bat .= "\r\n";
    $bat .= "echo  [3/4] Creation du raccourci Bureau...\r\n";
    $bat .= "powershell -Command \"\$ws = New-Object -ComObject WScript.Shell; \$s = \$ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\\Centre de Masse.lnk'); \$s.TargetPath = '%INSTALL_DIR%\\CentredeMasse.exe'; \$s.WorkingDirectory = '%INSTALL_DIR%'; \$s.IconLocation = '%INSTALL_DIR%\\CentredeMasse.exe,0'; \$s.Description = 'Centre de Masse - Plateforme de force'; \$s.Save()\"\r\n";
    $bat .= "echo         Raccourci cree sur le Bureau.\r\n";
    $bat .= "echo.\r\n";
    $bat .= "\r\n";
    $bat .= "echo  [4/4] Creation du raccourci Menu Demarrer...\r\n";
    $bat .= "set \"START_DIR=%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Centre de Masse\"\r\n";
    $bat .= "if not exist \"%START_DIR%\" mkdir \"%START_DIR%\"\r\n";
    $bat .= "powershell -Command \"\$ws = New-Object -ComObject WScript.Shell; \$s = \$ws.CreateShortcut('%START_DIR%\\Centre de Masse.lnk'); \$s.TargetPath = '%INSTALL_DIR%\\CentredeMasse.exe'; \$s.WorkingDirectory = '%INSTALL_DIR%'; \$s.IconLocation = '%INSTALL_DIR%\\CentredeMasse.exe,0'; \$s.Description = 'Centre de Masse - Plateforme de force'; \$s.Save()\"\r\n";
    $bat .= "echo         Raccourci cree dans le Menu Demarrer.\r\n";
    $bat .= "echo.\r\n";
    $bat .= "\r\n";
    $bat .= "echo.\r\n";
    $bat .= "color 0A\r\n";
    $bat .= "echo  ========================================\r\n";
    $bat .= "echo    Installation terminee avec succes !\r\n";
    $bat .= "echo  ========================================\r\n";
    $bat .= "echo.\r\n";
    $bat .= "echo  Dossier : %INSTALL_DIR%\r\n";
    $bat .= "echo  Raccourci : Bureau + Menu Demarrer\r\n";
    $bat .= "echo.\r\n";
    $bat .= "echo  L'application va se lancer...\r\n";
    $bat .= "timeout /t 3 >nul\r\n";
    $bat .= "start \"\" \"%INSTALL_DIR%\\CentredeMasse.exe\"\r\n";
    $bat .= "exit\r\n";

    header('Content-Type: application/octet-stream');
    header('Content-Disposition: attachment; filename="Installer_CentredeMasse.bat"');
    header('Content-Length: ' . strlen($bat));
    header('Cache-Control: no-cache');
    echo $bat;
    exit;
}

// ── POST (normal) — Receive heartbeat ────────────────────────
if ($_SERVER['REQUEST_METHOD'] === 'POST' && !isset($_GET['action'])) {
    if ($api_key_header !== API_KEY) {
        http_response_code(403);
        echo json_encode(['error' => 'Invalid API key']);
        exit;
    }

    $json = file_get_contents('php://input');
    $data = json_decode($json, true);

    if (!$data || !isset($data['app_id'])) {
        http_response_code(400);
        echo json_encode(['error' => 'Invalid payload']);
        exit;
    }

    $app_id = preg_replace('/[^a-zA-Z0-9_-]/', '', $data['app_id']);
    $filepath = DATA_DIR . '/' . $app_id . '.json';
    $data['server_time'] = date('Y-m-d H:i:s');

    file_put_contents($filepath, json_encode($data, JSON_PRETTY_PRINT));
    echo json_encode(['ok' => true]);
    exit;
}

// ── POST ?action=upload — Upload new .exe from admin dashboard ──
if ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_GET['action'] ?? '') === 'upload') {
    // Check admin password (POST field)
    $pwd = $_POST['admin_pwd'] ?? '';
    if ($pwd !== API_KEY) {
        $upload_error = "Mot de passe admin incorrect.";
    } elseif (!isset($_FILES['exe_file']) || $_FILES['exe_file']['error'] !== UPLOAD_ERR_OK) {
        $upload_error = "Erreur upload: " . ($_FILES['exe_file']['error'] ?? 'no file');
    } elseif ($_FILES['exe_file']['size'] > MAX_EXE_SIZE) {
        $upload_error = "Fichier trop gros (max " . (MAX_EXE_SIZE/1024/1024) . " MB)";
    } else {
        $new_version = intval($_POST['new_version'] ?? 0);
        if ($new_version < 1) {
            $upload_error = "Numero de version invalide.";
        } else {
            // Save exe
            move_uploaded_file($_FILES['exe_file']['tmp_name'],
                               UPDATE_DIR . '/CentredeMasse.exe');
            // Save version
            file_put_contents(UPDATE_DIR . '/version.json',
                              json_encode(['version' => $new_version], JSON_PRETTY_PRINT));
            $upload_success = "Version $new_version uploadee ! Les apps se mettront a jour dans ~5 min.";
        }
    }
}

// ── Dashboard (GET, no action) ───────────────────────────────
$apps = [];
if (is_dir(DATA_DIR)) {
    foreach (glob(DATA_DIR . '/*.json') as $file) {
        $data = json_decode(file_get_contents($file), true);
        if ($data) {
            $last = strtotime($data['server_time'] ?? '2000-01-01');
            $ago = time() - $last;
            $data['_alive'] = ($ago < 180 && ($data['status'] ?? '') === 'online');
            $data['_ago'] = $ago;
            $apps[] = $data;
        }
    }
}
usort($apps, function($a, $b) {
    if ($a['_alive'] !== $b['_alive']) return $b['_alive'] - $a['_alive'];
    return strcasecmp($a['app_name'] ?? '', $b['app_name'] ?? '');
});

// Current update version
$cur_update_ver = 0;
$ver_file = UPDATE_DIR . '/version.json';
if (file_exists($ver_file)) {
    $vd = json_decode(file_get_contents($ver_file), true);
    $cur_update_ver = $vd['version'] ?? 0;
}
$exe_exists = file_exists(UPDATE_DIR . '/CentredeMasse.exe');
$exe_size = $exe_exists ? filesize(UPDATE_DIR . '/CentredeMasse.exe') : 0;
?>
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Centre de Masse — Admin</title>
    <link rel="icon" type="image/png" href="favicon.png">
    <meta http-equiv="refresh" content="30">
    <style>
        :root {
            --bg: #0f172a; --card: #1e293b; --border: #334155;
            --blue: #38bdf8; --teal: #2dd4bf; --green: #4ade80;
            --amber: #fbbf24; --red: #fb7185;
            --text: #f1f5f9; --text2: #94a3b8; --dim: #475569;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
        .container { max-width: 1100px; margin: 0 auto; padding: 20px; }
        h1 { color: var(--blue); font-size: 22px; padding: 16px 0; border-bottom: 1px solid var(--border); margin-bottom: 20px; }
        h2 { color: var(--teal); font-size: 16px; margin-bottom: 12px; }
        .summary { display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
        .stat-box { background: var(--card); border: 1px solid var(--border); border-radius: 8px; padding: 14px 18px; min-width: 140px; }
        .stat-box .val { font-size: 28px; font-weight: bold; }
        .stat-box .label { font-size: 11px; color: var(--text2); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px; }
        .card { background: var(--card); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 16px; overflow: hidden; }
        .app-header { display: flex; align-items: center; gap: 12px; padding: 14px 18px; border-bottom: 1px solid var(--border); flex-wrap: wrap; }
        .app-header .dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
        .dot-on { background: var(--green); box-shadow: 0 0 8px rgba(74,222,128,0.5); }
        .dot-off { background: var(--red); }
        .app-header .name { font-size: 16px; font-weight: 600; }
        .app-header .meta { font-size: 12px; color: var(--dim); margin-left: auto; }
        .app-body { padding: 14px 18px; display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
        .metric .mv { font-size: 18px; font-weight: 600; font-family: 'Consolas', monospace; }
        .metric .ml { font-size: 11px; color: var(--text2); }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
        .b-green { background: rgba(74,222,128,0.15); color: var(--green); }
        .b-red { background: rgba(251,113,133,0.15); color: var(--red); }
        .b-amber { background: rgba(251,191,36,0.15); color: var(--amber); }
        .b-blue { background: rgba(56,189,248,0.15); color: var(--blue); }
        .b-teal { background: rgba(45,212,191,0.15); color: var(--teal); }
        table { width: 100%; border-collapse: collapse; margin-top: 8px; }
        th { text-align: left; padding: 4px 8px; font-size: 10px; color: var(--dim); text-transform: uppercase; border-bottom: 1px solid var(--border); }
        td { padding: 5px 8px; font-size: 12px; border-bottom: 1px solid rgba(51,65,85,0.5); }
        .section-title { font-size: 13px; color: var(--teal); font-weight: 600; margin: 10px 0 6px; }
        .empty { text-align: center; color: var(--dim); padding: 40px; }
        .update-box { padding: 18px; }
        .update-box input[type=file], .update-box input[type=number], .update-box input[type=password] {
            background: var(--bg); color: var(--text); border: 1px solid var(--border);
            border-radius: 6px; padding: 8px 10px; font-size: 13px; margin: 4px 0;
        }
        .update-box label { color: var(--text2); font-size: 13px; display: block; margin-top: 8px; }
        .btn { display: inline-block; padding: 8px 16px; border-radius: 6px; border: none;
            font-size: 13px; font-weight: 600; cursor: pointer; }
        .btn-blue { background: var(--blue); color: var(--bg); }
        .btn:hover { opacity: 0.85; }
        .alert-ok { background: rgba(74,222,128,0.15); color: var(--green); padding: 10px 14px; border-radius: 6px; margin: 10px 0; }
        .alert-err { background: rgba(251,113,133,0.15); color: var(--red); padding: 10px 14px; border-radius: 6px; margin: 10px 0; }
        @media (max-width: 600px) { .app-body { grid-template-columns: 1fr; } .summary { flex-direction: column; } }
    </style>
</head>
<body>
<div class="container">
    <h1>Centre de Masse — Admin</h1>

    <?php
    $total_apps = count($apps);
    $online_apps = count(array_filter($apps, function($a) { return $a['_alive']; }));
    $total_users = array_sum(array_column($apps, 'user_count'));
    $total_sessions = array_sum(array_column($apps, 'session_count'));
    $total_samples = array_sum(array_column($apps, 'sample_count'));
    ?>

    <div class="summary">
        <div class="stat-box"><div class="val" style="color: var(--blue);"><?= $total_apps ?></div><div class="label">Applications</div></div>
        <div class="stat-box"><div class="val" style="color: var(--green);"><?= $online_apps ?></div><div class="label">En ligne</div></div>
        <div class="stat-box"><div class="val" style="color: var(--teal);"><?= $total_users ?></div><div class="label">Utilisateurs</div></div>
        <div class="stat-box"><div class="val" style="color: var(--amber);"><?= $total_sessions ?></div><div class="label">Sessions</div></div>
        <div class="stat-box"><div class="val" style="color: var(--text2);"><?= number_format($total_samples) ?></div><div class="label">Samples</div></div>
    </div>

    <!-- ── MISE A JOUR ──────────────────────────────── -->
    <div class="card">
        <div class="update-box">
            <h2>Mise a jour a distance</h2>
            <p style="font-size: 13px; color: var(--text2); margin-bottom: 10px;">
                Upload un nouveau <code>CentredeMasse.exe</code> ici.
                Toutes les apps en ligne se mettront a jour automatiquement (dans ~5 min).
            </p>

            <div style="display: flex; gap: 16px; align-items: center; flex-wrap: wrap; margin-bottom: 12px;">
                <div>
                    <span style="color: var(--text2); font-size: 12px;">Version actuelle sur le serveur :</span>
                    <span class="badge <?= $cur_update_ver > 0 ? 'b-teal' : 'b-red' ?>" style="font-size: 14px;">
                        <?= $cur_update_ver > 0 ? "v$cur_update_ver" : 'Aucune' ?>
                    </span>
                </div>
                <?php if ($exe_exists): ?>
                <div>
                    <span style="color: var(--text2); font-size: 12px;">Taille .exe :</span>
                    <span style="color: var(--text); font-size: 13px;"><?= round($exe_size/1024/1024, 1) ?> MB</span>
                </div>
                <?php endif; ?>
            </div>

            <?php if (!empty($upload_success)): ?>
                <div class="alert-ok"><?= htmlspecialchars($upload_success) ?></div>
            <?php endif; ?>
            <?php if (!empty($upload_error)): ?>
                <div class="alert-err"><?= htmlspecialchars($upload_error) ?></div>
            <?php endif; ?>

            <form method="POST" action="?action=upload" enctype="multipart/form-data">
                <label>Nouveau numero de version (entier, > version actuelle) :</label>
                <input type="number" name="new_version" min="1" value="<?= $cur_update_ver + 1 ?>" style="width: 80px;">

                <label>Fichier .exe :</label>
                <input type="file" name="exe_file" accept=".exe">

                <label>Mot de passe admin :</label>
                <input type="password" name="admin_pwd" placeholder="Cle API">

                <br><br>
                <button type="submit" class="btn btn-blue">Uploader la mise a jour</button>
            </form>
        </div>
    </div>

    <!-- ── APPS ─────────────────────────────────────── -->
    <?php if (empty($apps)): ?>
        <div class="empty">
            <p>Aucune application connectee.</p>
        </div>
    <?php else: ?>
        <?php foreach ($apps as $app): ?>
        <div class="card">
            <div class="app-header">
                <div class="dot <?= $app['_alive'] ? 'dot-on' : 'dot-off' ?>"></div>
                <span class="name"><?= htmlspecialchars($app['app_name'] ?? 'Inconnu') ?></span>

                <?php if ($app['_alive']): ?>
                    <span class="badge b-green">EN LIGNE</span>
                <?php else: ?>
                    <span class="badge b-red">HORS LIGNE</span>
                <?php endif; ?>

                <?php if (!empty($app['is_recording'])): ?>
                    <span class="badge b-amber">ENREGISTREMENT</span>
                <?php endif; ?>

                <?php if (!empty($app['connected'])): ?>
                    <span class="badge b-blue">CONNECTE</span>
                <?php endif; ?>

                <span class="badge b-teal">v<?= $app['app_version'] ?? '?' ?></span>

                <span class="meta">
                    <?= htmlspecialchars($app['hostname'] ?? '') ?>
                    &middot; <?= htmlspecialchars($app['os'] ?? '') ?>
                    &middot; ID: <?= htmlspecialchars($app['app_id'] ?? '') ?>
                    <?php if ($app['_ago'] < 60): ?>
                        &middot; il y a <?= $app['_ago'] ?>s
                    <?php elseif ($app['_ago'] < 3600): ?>
                        &middot; il y a <?= intval($app['_ago']/60) ?>min
                    <?php else: ?>
                        &middot; il y a <?= intval($app['_ago']/3600) ?>h
                    <?php endif; ?>
                </span>
            </div>

            <div class="app-body">
                <div class="metric">
                    <div class="mv" style="color: var(--teal);"><?= $app['user_count'] ?? 0 ?></div>
                    <div class="ml">Utilisateurs</div>
                </div>
                <div class="metric">
                    <div class="mv" style="color: var(--blue);"><?= $app['platform_count'] ?? 0 ?></div>
                    <div class="ml">Plateformes</div>
                </div>
                <div class="metric">
                    <div class="mv" style="color: var(--amber);"><?= $app['session_count'] ?? 0 ?></div>
                    <div class="ml">Sessions</div>
                </div>
                <div class="metric">
                    <div class="mv" style="color: var(--text2);"><?= number_format($app['sample_count'] ?? 0) ?></div>
                    <div class="ml">Samples</div>
                </div>
                <div class="metric">
                    <?php
                    $dur = $app['total_duration_sec'] ?? 0;
                    if ($dur >= 3600) $dur_str = intval($dur/3600).'h '.intval(($dur%3600)/60).'min';
                    elseif ($dur >= 60) $dur_str = intval($dur/60).'min '.intval($dur%60).'s';
                    else $dur_str = round($dur, 1).'s';
                    ?>
                    <div class="mv" style="color: var(--green);"><?= $dur_str ?></div>
                    <div class="ml">Duree totale</div>
                </div>
                <div class="metric">
                    <div class="mv" style="color: var(--dim);"><?= htmlspecialchars($app['timestamp'] ?? '--') ?></div>
                    <div class="ml">Dernier signal</div>
                </div>
            </div>

            <?php if (!empty($app['users'])): ?>
            <div style="padding: 0 18px 8px;">
                <div class="section-title">Utilisateurs</div>
                <table>
                    <tr><th>Nom</th><th>Sessions</th><th>Samples</th><th>Duree</th></tr>
                    <?php foreach ($app['users'] as $u): ?>
                    <tr>
                        <td><?= htmlspecialchars($u['name']) ?></td>
                        <td><?= $u['sessions'] ?></td>
                        <td><?= number_format($u['samples']) ?></td>
                        <td><?php $d=$u['duration_sec']; echo ($d>=60)?intval($d/60).'min '.intval($d%60).'s':round($d,1).'s'; ?></td>
                    </tr>
                    <?php endforeach; ?>
                </table>
            </div>
            <?php endif; ?>

            <?php if (!empty($app['platforms'])): ?>
            <div style="padding: 0 18px 8px;">
                <div class="section-title">Plateformes</div>
                <table>
                    <tr><th>Nom</th><th>Sessions</th><th>Samples</th><th>Duree</th></tr>
                    <?php foreach ($app['platforms'] as $p): ?>
                    <tr>
                        <td><?= htmlspecialchars($p['name']) ?></td>
                        <td><?= $p['sessions'] ?></td>
                        <td><?= number_format($p['samples']) ?></td>
                        <td><?php $d=$p['duration_sec']; echo ($d>=60)?intval($d/60).'min '.intval($d%60).'s':round($d,1).'s'; ?></td>
                    </tr>
                    <?php endforeach; ?>
                </table>
            </div>
            <?php endif; ?>

            <?php if (!empty($app['recent_sessions'])): ?>
            <div style="padding: 0 18px 14px;">
                <div class="section-title">Dernieres sessions</div>
                <table>
                    <tr><th>#</th><th>Date</th><th>Utilisateur</th><th>Plateforme</th><th>Duree</th><th>Samples</th></tr>
                    <?php foreach ($app['recent_sessions'] as $s): ?>
                    <tr>
                        <td><?= $s['id'] ?></td>
                        <td><?= htmlspecialchars($s['started_at'] ?? '') ?></td>
                        <td><?= htmlspecialchars($s['user_name'] ?? '?') ?></td>
                        <td><?= htmlspecialchars($s['platform_name'] ?? '?') ?></td>
                        <td><?php $d=$s['duration_sec']??0; echo ($d>=60)?intval($d/60).'m '.intval($d%60).'s':round($d,1).'s'; ?></td>
                        <td><?= $s['sample_count'] ?? 0 ?></td>
                    </tr>
                    <?php endforeach; ?>
                </table>
            </div>
            <?php endif; ?>
        </div>
        <?php endforeach; ?>
    <?php endif; ?>

    <div style="text-align: center; padding: 20px; color: var(--dim); font-size: 12px;">
        Auto-refresh 30s &middot; <?= count($apps) ?> app(s) &middot; <?= date('H:i:s') ?>
    </div>
</div>
</body>
</html>
