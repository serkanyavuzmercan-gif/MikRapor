"""
GECICI TESHIS — Windows runner'da Store WinRT yuzeyini olcer.

Neden var: masaustu uygulamasinda RequestPurchaseAsync pencere tanitici (HWND)
baglamasi ister ve bunu Python'dan hangi sembolle yapacagimizi BILMIYORUZ.
Sekme cubugu vakasinda oldugu gibi tahmin etmiyoruz: runner'a soruyoruz.

Bastirdiklari:
  1. windows.services.store'u hangi PyPI paketi sagliyor (winsdk / winrt-*)
  2. StoreContext uzerinde interop (initialize_with_window benzeri) sembol var mi
  3. Thread'in COM apartman durumu (STA/MTA) — QApplication oncesi ve sonrasi

ASCII-only: runner konsolu cp1252, Turkce karakter UnicodeEncodeError atiyor.
"""

import ctypes
import importlib
import sys


def apartman(etiket):
    """CoGetApartmentType -> STA/MTA. IInitializeWithWindow STA bekler."""
    adlar = {0: "STA", 1: "MTA", 2: "NA", 3: "MAINSTA"}
    try:
        apt = ctypes.c_int()
        qual = ctypes.c_int()
        hr = ctypes.windll.ole32.CoGetApartmentType(
            ctypes.byref(apt), ctypes.byref(qual))
        if hr != 0:
            print(f"  apartman ({etiket}): HRESULT 0x{hr & 0xFFFFFFFF:08X} "
                  f"(0x800401F0 = CoInitialize yapilmamis)")
            return
        print(f"  apartman ({etiket}): {adlar.get(apt.value, apt.value)} "
              f"qualifier={qual.value}")
    except Exception as e:
        print(f"  apartman ({etiket}): olculemedi: {e}")


def paketi_dene(modul_adi):
    try:
        m = importlib.import_module(modul_adi)
    except Exception as e:
        print(f"  {modul_adi:42s} YOK  ({type(e).__name__})")
        return None
    surum = getattr(m, "__version__", "?")
    print(f"  {modul_adi:42s} VAR  surum={surum}")
    return m


def interop_ara(modul, sinif):
    """initialize_with_window benzeri her sembolu listele."""
    anahtarlar = ("initialize", "window", "interop", "hwnd", "iunknown")
    bulunan = []
    for kaynak, ad in ((modul, "modul"), (sinif, "StoreContext")):
        if kaynak is None:
            continue
        for s in dir(kaynak):
            if any(a in s.lower() for a in anahtarlar):
                bulunan.append(f"{ad}.{s}")
    print("  interop adaylari:", bulunan or "HICBIRI")


def main():
    print("python:", sys.version)
    print("platform:", sys.platform)

    print("\n[1] windows.services.store'u kim sagliyor?")
    adaylar = [
        "winsdk",
        "winsdk.windows.services.store",
        "winrt",
        "winrt.windows.services.store",
        "winrt.windows.foundation",
    ]
    magaza_modul = None
    for ad in adaylar:
        m = paketi_dene(ad)
        if ad.endswith("services.store") and m is not None:
            magaza_modul = m

    print("\n[2] StoreContext yuzeyi")
    if magaza_modul is None:
        print("  StoreContext'e ulasilamadi — satin alma yolu yazilamaz.")
    else:
        sc = getattr(magaza_modul, "StoreContext", None)
        print("  StoreContext:", sc)
        if sc is not None:
            uyeler = [s for s in dir(sc) if not s.startswith("_")]
            print("  uye sayisi:", len(uyeler))
            print("  request/purchase iceren:",
                  [s for s in uyeler if "purchase" in s.lower()
                   or "request" in s.lower()])
        interop_ara(magaza_modul, sc)

    print("\n[3] interop modulleri")
    for ad in ("winsdk._winrt", "winrt._winrt", "winsdk.system",
               "winrt.system", "winsdk.windows.foundation"):
        m = paketi_dene(ad)
        if m is not None:
            print("     ->", [s for s in dir(m)
                              if "window" in s.lower() or "initial" in s.lower()])

    print("\n[4] COM apartmani")
    apartman("QApplication oncesi")
    try:
        from PyQt6.QtWidgets import QApplication
        _ = QApplication(sys.argv[:1])
        apartman("QApplication sonrasi")
    except Exception as e:
        print("  QApplication kurulamadi:", e)


if __name__ == "__main__":
    main()
