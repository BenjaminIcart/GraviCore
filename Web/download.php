<?php
/**
 * Centre de Masse — Public Download Page
 *
 * Upload to: https://ibenji.fr/plancheadmin/download.php
 * Public URL for users: https://ibenji.fr/plancheadmin/download.php
 */

define('UPDATE_DIR', __DIR__ . '/cm_updates');
define('DATA_DIR',   __DIR__ . '/cm_data');

// Gather version + file info
$cur_version = 0;
$ver_file = UPDATE_DIR . '/version.json';
if (file_exists($ver_file)) {
    $vd = json_decode(file_get_contents($ver_file), true);
    $cur_version = $vd['version'] ?? 0;
}

$exe_path   = UPDATE_DIR . '/CentredeMasse.exe';
$exe_exists = file_exists($exe_path);
$exe_size   = $exe_exists ? filesize($exe_path) : 0;
$exe_size_mb = round($exe_size / 1024 / 1024, 1);
$exe_date   = $exe_exists ? date('d/m/Y', filemtime($exe_path)) : '--';

// Download counts
$dl_exe_file = DATA_DIR . '/_download_count.txt';
$dl_inst_file = DATA_DIR . '/_installer_count.txt';
$dl_total = 0;
if (file_exists($dl_exe_file))  $dl_total += intval(file_get_contents($dl_exe_file));
if (file_exists($dl_inst_file)) $dl_total += intval(file_get_contents($dl_inst_file));

// Build URLs
$proto = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
$host  = $_SERVER['HTTP_HOST'];
$base  = dirname($_SERVER['SCRIPT_NAME']);
$installer_url = "$proto://$host$base/cm_api.php?action=installer";
$direct_url    = "$proto://$host$base/cm_api.php?action=public_download";
?>
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Centre de Masse — Telecharger</title>
    <link rel="icon" type="image/png" href="favicon.png">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0a0e1a;
            --bg2: #0f1629;
            --card: #151d33;
            --card-hover: #1a2440;
            --border: #1e2d4a;
            --blue: #38bdf8;
            --blue-dim: rgba(56,189,248,0.12);
            --teal: #2dd4bf;
            --teal-dim: rgba(45,212,191,0.12);
            --green: #4ade80;
            --green-dim: rgba(74,222,128,0.12);
            --amber: #fbbf24;
            --purple: #a78bfa;
            --purple-dim: rgba(167,139,250,0.12);
            --text: #f1f5f9;
            --text2: #94a3b8;
            --dim: #475569;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* ── Animated background ── */
        .bg-glow {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            pointer-events: none; z-index: 0; overflow: hidden;
        }
        .bg-glow .orb {
            position: absolute; border-radius: 50%; filter: blur(120px); opacity: 0.15;
        }
        .bg-glow .orb-1 { width: 600px; height: 600px; background: var(--blue); top: -200px; right: -100px; animation: float1 20s ease-in-out infinite; }
        .bg-glow .orb-2 { width: 500px; height: 500px; background: var(--teal); bottom: -150px; left: -100px; animation: float2 25s ease-in-out infinite; }
        .bg-glow .orb-3 { width: 400px; height: 400px; background: var(--purple); top: 50%; left: 50%; transform: translate(-50%,-50%); animation: float3 18s ease-in-out infinite; }

        @keyframes float1 { 0%,100% { transform: translate(0,0); } 50% { transform: translate(-80px, 60px); } }
        @keyframes float2 { 0%,100% { transform: translate(0,0); } 50% { transform: translate(60px, -80px); } }
        @keyframes float3 { 0%,100% { transform: translate(-50%,-50%) scale(1); } 50% { transform: translate(-50%,-50%) scale(1.2); } }

        .container {
            position: relative; z-index: 1;
            max-width: 880px; margin: 0 auto;
            padding: 40px 24px 60px;
        }

        /* ── Header / Hero ── */
        .hero { text-align: center; margin-bottom: 48px; }
        .hero-icon {
            width: 88px; height: 88px; border-radius: 22px;
            background: linear-gradient(135deg, var(--blue), var(--teal));
            display: inline-flex; align-items: center; justify-content: center;
            margin-bottom: 24px; box-shadow: 0 8px 40px rgba(56,189,248,0.25);
        }
        .hero-icon svg { width: 48px; height: 48px; fill: white; }
        .hero h1 {
            font-size: 42px; font-weight: 800; letter-spacing: -1px;
            background: linear-gradient(135deg, var(--blue), var(--teal));
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            background-clip: text; margin-bottom: 12px;
        }
        .hero .subtitle {
            font-size: 18px; color: var(--text2); font-weight: 400;
            max-width: 540px; margin: 0 auto; line-height: 1.6;
        }

        /* ── Download card ── */
        .dl-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 36px;
            margin-bottom: 32px;
            text-align: center;
        }

        .dl-buttons { display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; margin-bottom: 24px; }

        .btn {
            display: inline-flex; align-items: center; gap: 10px;
            padding: 16px 32px; border-radius: 12px; border: none;
            font-size: 16px; font-weight: 600; cursor: pointer;
            text-decoration: none; transition: all 0.2s;
            font-family: inherit;
        }
        .btn svg { width: 22px; height: 22px; flex-shrink: 0; }

        .btn-primary {
            background: linear-gradient(135deg, var(--blue), #0ea5e9);
            color: white;
            box-shadow: 0 4px 24px rgba(56,189,248,0.3);
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 32px rgba(56,189,248,0.4);
        }

        .btn-secondary {
            background: var(--bg2);
            color: var(--text2);
            border: 1px solid var(--border);
        }
        .btn-secondary:hover {
            background: var(--card-hover);
            color: var(--text);
            border-color: var(--dim);
        }

        .dl-meta {
            display: flex; gap: 24px; justify-content: center; flex-wrap: wrap;
            font-size: 13px; color: var(--dim);
        }
        .dl-meta span { display: inline-flex; align-items: center; gap: 6px; }
        .dl-meta svg { width: 14px; height: 14px; fill: currentColor; opacity: 0.7; }

        .install-info {
            margin-top: 20px; padding: 16px 20px;
            background: var(--teal-dim);
            border: 1px solid rgba(45,212,191,0.2);
            border-radius: 10px; text-align: left;
            font-size: 13px; color: var(--teal); line-height: 1.6;
        }
        .install-info code {
            background: rgba(0,0,0,0.3); padding: 2px 8px; border-radius: 4px;
            font-family: 'Consolas', 'Courier New', monospace; font-size: 12px;
        }

        /* ── Features grid ── */
        .features-title {
            text-align: center; font-size: 24px; font-weight: 700;
            margin-bottom: 24px; color: var(--text);
        }
        .features {
            display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px; margin-bottom: 40px;
        }
        .feat {
            background: var(--card); border: 1px solid var(--border);
            border-radius: 12px; padding: 22px;
            transition: border-color 0.2s, transform 0.2s;
        }
        .feat:hover { border-color: var(--dim); transform: translateY(-2px); }
        .feat-icon {
            width: 40px; height: 40px; border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            margin-bottom: 12px; font-size: 20px;
        }
        .feat h3 { font-size: 15px; font-weight: 600; margin-bottom: 6px; }
        .feat p { font-size: 13px; color: var(--text2); line-height: 1.5; }

        /* ── Steps ── */
        .steps-card {
            background: var(--card); border: 1px solid var(--border);
            border-radius: 16px; padding: 32px; margin-bottom: 32px;
        }
        .steps-card h2 { font-size: 20px; font-weight: 700; margin-bottom: 20px; text-align: center; }
        .steps { display: flex; gap: 20px; flex-wrap: wrap; justify-content: center; }
        .step {
            flex: 1; min-width: 180px; max-width: 240px;
            text-align: center; padding: 16px;
        }
        .step-num {
            width: 36px; height: 36px; border-radius: 50%;
            background: var(--blue-dim); color: var(--blue);
            display: inline-flex; align-items: center; justify-content: center;
            font-size: 16px; font-weight: 700; margin-bottom: 12px;
        }
        .step h3 { font-size: 14px; font-weight: 600; margin-bottom: 6px; }
        .step p { font-size: 12px; color: var(--text2); line-height: 1.5; }

        /* ── Requirements ── */
        .req {
            background: var(--card); border: 1px solid var(--border);
            border-radius: 12px; padding: 24px; margin-bottom: 32px;
        }
        .req h3 { font-size: 15px; font-weight: 600; margin-bottom: 12px; color: var(--amber); }
        .req-list { list-style: none; display: flex; flex-wrap: wrap; gap: 10px; }
        .req-list li {
            background: var(--bg2); border: 1px solid var(--border);
            border-radius: 8px; padding: 8px 14px;
            font-size: 13px; color: var(--text2);
            display: flex; align-items: center; gap: 8px;
        }
        .req-list li::before { content: "✓"; color: var(--green); font-weight: 700; }

        /* ── No file state ── */
        .no-file {
            text-align: center; padding: 40px;
            background: var(--card); border: 1px solid var(--border);
            border-radius: 16px; margin-bottom: 32px;
        }
        .no-file p { color: var(--dim); font-size: 16px; }

        /* ── Footer ── */
        .footer {
            text-align: center; padding: 24px;
            color: var(--dim); font-size: 12px;
            border-top: 1px solid var(--border);
        }

        @media (max-width: 600px) {
            .hero h1 { font-size: 28px; }
            .hero .subtitle { font-size: 15px; }
            .dl-card { padding: 24px 16px; }
            .btn { padding: 14px 24px; font-size: 14px; width: 100%; justify-content: center; }
            .dl-buttons { flex-direction: column; }
            .steps { flex-direction: column; align-items: center; }
        }
    </style>
</head>
<body>
    <div class="bg-glow">
        <div class="orb orb-1"></div>
        <div class="orb orb-2"></div>
        <div class="orb orb-3"></div>
    </div>

    <div class="container">
        <!-- ── Hero ── -->
        <div class="hero">
            <div class="hero-icon">
                <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8z"/>
                    <circle cx="12" cy="12" r="3"/>
                    <path d="M12 6v2M12 16v2M6 12h2M16 12h2" stroke="white" stroke-width="2" fill="none" stroke-linecap="round"/>
                </svg>
            </div>
            <h1>Centre de Masse</h1>
            <p class="subtitle">
                Application d'analyse de plateforme de force.
                Visualisez votre centre de pression en temps reel,
                enregistrez vos sessions et suivez votre progression.
            </p>
        </div>

        <!-- ── Download card ── -->
        <?php if ($exe_exists): ?>
        <div class="dl-card">
            <div class="dl-buttons">
                <a href="<?= htmlspecialchars($installer_url) ?>" class="btn btn-primary" id="btn-install">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <polyline points="7 10 12 15 17 10"/>
                        <line x1="12" y1="15" x2="12" y2="3"/>
                    </svg>
                    Installer
                </a>
                <a href="<?= htmlspecialchars($direct_url) ?>" class="btn btn-secondary">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                        <line x1="12" y1="18" x2="12" y2="12"/>
                        <polyline points="9 15 12 18 15 15"/>
                    </svg>
                    .exe seul
                </a>
            </div>

            <div class="dl-meta">
                <span>
                    <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
                    Version <?= $cur_version ?>
                </span>
                <span>
                    <svg viewBox="0 0 24 24"><path d="M20 6h-8l-2-2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2z"/></svg>
                    <?= $exe_size_mb ?> MB
                </span>
                <span>
                    <svg viewBox="0 0 24 24"><path d="M19 3h-1V1h-2v2H8V1H6v2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V8h14v11z"/></svg>
                    <?= $exe_date ?>
                </span>
                <span>
                    <svg viewBox="0 0 24 24"><path d="M16.5 3c-1.74 0-3.41.81-4.5 2.09C10.91 3.81 9.24 3 7.5 3 4.42 3 2 5.42 2 8.5c0 3.78 3.4 6.86 8.55 11.54L12 21.35l1.45-1.32C18.6 15.36 22 12.28 22 8.5 22 5.42 19.58 3 16.5 3z"/></svg>
                    <?= number_format($dl_total) ?> telechargements
                </span>
            </div>

            <div class="install-info">
                <strong>Installation automatique :</strong> Le bouton « Installer » telecharge un petit script
                qui installe l'application dans
                <code>%LocalAppData%\Programs\CentredeMasse\</code>
                et cree un raccourci sur le Bureau et dans le Menu Demarrer.
                <br>
                Le bouton « .exe seul » telecharge uniquement l'executable sans installation.
            </div>
        </div>
        <?php else: ?>
        <div class="no-file">
            <p>L'application n'est pas encore disponible au telechargement.</p>
            <p style="font-size: 13px; margin-top: 8px; color: var(--dim);">Revenez bientot !</p>
        </div>
        <?php endif; ?>

        <!-- ── How to install ── -->
        <div class="steps-card">
            <h2>Installation en 3 etapes</h2>
            <div class="steps">
                <div class="step">
                    <div class="step-num">1</div>
                    <h3>Telecharger</h3>
                    <p>Cliquez sur « Installer » ci-dessus. Votre navigateur peut afficher un avertissement : choisissez « Conserver ».</p>
                </div>
                <div class="step">
                    <div class="step-num">2</div>
                    <h3>Executer</h3>
                    <p>Double-cliquez sur le fichier <strong>Installer_CentredeMasse.bat</strong>. Si Windows SmartScreen s'affiche, cliquez « Informations complementaires » puis « Executer quand meme ».</p>
                </div>
                <div class="step">
                    <div class="step-num">3</div>
                    <h3>Utiliser</h3>
                    <p>L'application se lance automatiquement. Un raccourci « Centre de Masse » est cree sur votre Bureau.</p>
                </div>
            </div>
        </div>

        <!-- ── Features ── -->
        <h2 class="features-title">Fonctionnalites</h2>
        <div class="features">
            <div class="feat">
                <div class="feat-icon" style="background: var(--blue-dim); color: var(--blue);">&#9678;</div>
                <h3>Centre de pression en temps reel</h3>
                <p>Visualisez votre centre de masse sur la plateforme avec une croix animee et une trace du mouvement.</p>
            </div>
            <div class="feat">
                <div class="feat-icon" style="background: rgba(251,113,133,0.12); color: #fb7185;">&#9679;</div>
                <h3>4 capteurs de force</h3>
                <p>Lecture simultanee des 4 capteurs avec affichage du poids par zone et poids total en kg.</p>
            </div>
            <div class="feat">
                <div class="feat-icon" style="background: var(--green-dim); color: var(--green);">&#9654;</div>
                <h3>Enregistrement de sessions</h3>
                <p>Enregistrez vos mesures en un clic, puis rejouez-les avec controle de vitesse et timeline.</p>
            </div>
            <div class="feat">
                <div class="feat-icon" style="background: var(--purple-dim); color: var(--purple);">&#9734;</div>
                <h3>Multi-utilisateurs</h3>
                <p>Creez des profils utilisateurs et des plateformes pour organiser vos donnees.</p>
            </div>
            <div class="feat">
                <div class="feat-icon" style="background: var(--teal-dim); color: var(--teal);">&#9729;</div>
                <h3>Dashboard web</h3>
                <p>Consultez et rejouez vos sessions depuis un navigateur grace au dashboard integre.</p>
            </div>
            <div class="feat">
                <div class="feat-icon" style="background: rgba(251,191,36,0.12); color: var(--amber);">&#8635;</div>
                <h3>Mises a jour automatiques</h3>
                <p>L'application se met a jour toute seule quand une nouvelle version est disponible.</p>
            </div>
        </div>

        <!-- ── Requirements ── -->
        <div class="req">
            <h3>Configuration requise</h3>
            <ul class="req-list">
                <li>Windows 10 / 11</li>
                <li>Bluetooth ou port USB</li>
                <li>Plateforme de force (ESP32 + 4 capteurs)</li>
                <li>50 MB d'espace disque</li>
            </ul>
        </div>

        <!-- ── Footer ── -->
        <div class="footer">
            Centre de Masse &copy; <?= date('Y') ?> &middot; Plateforme de force
        </div>
    </div>
</body>
</html>
