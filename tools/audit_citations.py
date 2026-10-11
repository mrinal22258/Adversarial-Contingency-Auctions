import re

with open('paper.tex', 'r', encoding='utf-8') as f:
    paper_txt = f.read()

with open('supplement.tex', 'r', encoding='utf-8') as f:
    supp_txt = f.read()

with open('references.bib', 'r', encoding='utf-8') as f:
    bib_txt = f.read()

bib_keys = set(re.findall(r'@\w+\s*\{\s*([^,]+),', bib_txt))

cites_paper = set()
for m in re.finditer(r'\\cite\{([^}]+)\}', paper_txt):
    for k in m.group(1).split(','):
        cites_paper.add(k.strip())

cites_supp = set()
for m in re.finditer(r'\\cite\{([^}]+)\}', supp_txt):
    for k in m.group(1).split(','):
        cites_supp.add(k.strip())

all_cites = cites_paper | cites_supp

print(f'Total bib keys: {len(bib_keys)}')
print(f'Cited in paper: {len(cites_paper)}')
print(f'Cited in supplement: {len(cites_supp)}')
print(f'Total cited: {len(all_cites)}')
print('\nBib keys NOT cited anywhere:')
for k in sorted(bib_keys - all_cites):
    print(f'  - {k}')

print('\nCites in paper/supp missing from bib:')
for k in sorted(all_cites - bib_keys):
    print(f'  - {k}')
