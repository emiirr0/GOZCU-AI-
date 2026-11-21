"""python -m gozcu — eksik kurulumda anlaşılır mesaj verir."""
import sys

try:
    from .cli import main
except ImportError as e:
    eksik = getattr(e, "name", "") or str(e)
    print(f"Gerekli kütüphane eksik: {eksik}\n"
          "Windows: 1_KURULUM.bat dosyasına çift tıkla.\n"
          "Diğer: python -m pip install -r requirements.txt\n"
          "Raspberry Pi: sudo apt install python3-opencv python3-numpy")
    sys.exit(1)

sys.exit(main())
