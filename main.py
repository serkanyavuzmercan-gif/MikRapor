#!/usr/bin/env python3
"""
MikRapor — Mikro ERP finansal raporlama (PyQt6) giriş noktası.

Uygulama kodu katmanlı paketlerdedir:
  domain/ — rapor motorları (saf hesaplama; GUI/ağ yok)
  infra/  — yapılandırma + Mikro REST istemcisi + veri çekme (SQL)
  ui/     — pencere, sekmeler (ui/tabs/*), görünümler, PDF, tema

Bu dosya yalnızca PyInstaller/komut satırı girişidir; bkz. ui.app.main().
"""

from __future__ import annotations

import sys

from ui.app import main

if __name__ == "__main__":
    sys.exit(main())
