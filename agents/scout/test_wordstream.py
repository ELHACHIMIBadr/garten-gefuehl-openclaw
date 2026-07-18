"""Test rapide WordStream scraper"""
import sys
sys.path.insert(0, '/root/garten-gefuehl-openclaw')

from wordstream_scraper import get_wordstream_volumes

results = get_wordstream_volumes("Balkonpflanzen", "DE")
print(f"\n=== RÉSULTATS ({len(results)} keywords) ===")
for r in results[:10]:
    print(f"  {r['keyword']:<40} vol={r['volume']:>6}  cpc={r['cpc']}  comp={r['competition']}")
