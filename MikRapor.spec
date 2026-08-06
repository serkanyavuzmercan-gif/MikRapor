# -*- mode: python ; coding: utf-8 -*-
# Tek kaynak: build_exe.ps1 bu spec'i çağırır. Asset / hiddenimport / exclude buradan yönetilir.
#
# İKİ ÇIKTI BİÇİMİ, TEK SPEC:
#   • onefile (varsayılan)  — doğrudan indirilen tek dosya MikRapor.exe
#   • onedir  (MIKRAPOR_ONEDIR=1) — MSIX'in içine giren klasör
# MSIX'e onefile koymak her açılışta paketi geçici klasöre açtırır: yavaş açılış ve
# mağaza sertifikasyonunda risk. Biçimi ortam değişkeni seçer ki `datas` listesi TEK
# yerde kalsın — ikinci bir spec dosyası, asset listesinin sessizce ayrışması demekti
# (bkz. test_paketleme).
import os

ONEDIR = os.environ.get("MIKRAPOR_ONEDIR") == "1"

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets\\icon.ico', 'assets'),
        ('assets\\logo.png', 'assets'),
        ('assets\\logo-mark.png', 'assets'),
        ('assets\\empty-hero.png', 'assets'),
        ('assets\\empty-bilanco.png', 'assets'),
        ('assets\\empty-gelir.png', 'assets'),
        ('assets\\empty-nakit.png', 'assets'),
        ('assets\\empty-nakit-kar.png', 'assets'),
        ('assets\\empty-tahmin.png', 'assets'),
        ('assets\\empty-tahsilat.png', 'assets'),
        ('assets\\empty-trendler.png', 'assets'),
        ('assets\\ai.png', 'assets'),
        ('assets\\anasayfalogo.png', 'assets'),
        # Açılır kutu oku — ARTIK ÇALIŞMA ANINDA ÜRETİLMİYOR. MSIX'te kurulum dizini
        # salt-okunur olduğu için üretim sessizce başarısız olup oku siliyordu.
        ('assets\\chevron-down-teal.png', 'assets'),
        ('assets\\mikrapor-hero-illustration.png', 'assets'),
        ('assets\\fonts\\DejaVuSans.ttf', 'assets\\fonts'),
        ('assets\\fonts\\DejaVuSans-Bold.ttf', 'assets\\fonts'),
        ('assets\\fonts\\LICENSE_DEJAVU', 'assets\\fonts'),
    ],
    hiddenimports=[
        'matplotlib.backends.backend_qtagg',
        'reportlab',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtNetwork',
        # Store köprüsü dinamik import ediyor; PyInstaller statik taramada göremez.
        # Bildirilmezse paketlenmiş uygulamada ImportError -> lisans hiç okunmaz ->
        # ÖDEYEN müşteride bile premium açılmaz, üstelik sessizce.
        'winsdk',
        'winsdk._winrt',
        'winsdk.windows.services.store',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt6.Qt3DAnimation',
        'PyQt6.Qt3DCore',
        'PyQt6.Qt3DExtras',
        'PyQt6.Qt3DInput',
        'PyQt6.Qt3DLogic',
        'PyQt6.Qt3DRender',
        'PyQt6.QtWebEngine',
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtQml',
        'PyQt6.QtQuick',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# onedir'de binaries/datas EXE'ye GÖMÜLMEZ, COLLECT ile klasöre yazılır.
_govde = [] if ONEDIR else [a.binaries, a.datas]

exe = EXE(
    pyz,
    a.scripts,
    *_govde,
    [],
    exclude_binaries=ONEDIR,
    name='MikRapor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icon.ico'],
)

if ONEDIR:
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name='MikRapor',
    )
