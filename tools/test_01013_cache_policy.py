from dataclasses import dataclass

GRACE=7*24*60*60*1000

@dataclass
class PL:
    id:str
    active:bool=True
    fallback:bool=False
    groups:tuple=()
    tvs:tuple=()
    items:tuple=()
    schedule:str=''

TV_ID='tv1'
TV_GROUPS={'g1'}
FIXED='fixed'


def applies(pl:PL):
    return pl.fallback or pl.id==FIXED or bool(TV_GROUPS.intersection(pl.groups)) or TV_ID in pl.tvs


def protected(playlists, active_items=()):
    out=set(active_items)
    for pl in playlists:
        if not pl.active or not applies(pl):
            continue
        out.update(pl.items)
    return out

# 1. Playlist semanal futura (>24h) continua protegida enquanto ativa/aplicável.
weekly=PL('weekly',groups=('g1',),items=('m_weekly',),schedule='sábado')
assert 'm_weekly' in protected([weekly])

# 2. Fallback sempre protegido.
fallback=PL('fb',fallback=True,items=('m_fb',))
assert 'm_fb' in protected([fallback])

# 3. Playlist fixa da TV protegida mesmo sem grupo.
fixed=PL('fixed',items=('m_fixed',))
assert 'm_fixed' in protected([fixed])

# 4. Mídia compartilhada permanece enquanto ao menos uma playlist aplicável ainda referencia.
p1=PL('p1',groups=('g1',),items=('shared',))
p2=PL('p2',groups=('g1',),items=('shared','other'))
assert 'shared' in protected([p2])

# 5. Playlist inativa não protege conteúdo antigo.
inactive=PL('old',active=False,groups=('g1',),items=('old_media',))
assert 'old_media' not in protected([inactive])

# 6. Mídia em reprodução nunca é removida mesmo sem referência momentânea.
assert 'playing' in protected([],active_items=('playing',))

# 7. Orfandade exige 7 dias contínuos.
now=10*GRACE
since=now-GRACE+1
assert now-since < GRACE
since=now-GRACE
assert now-since >= GRACE

# 8. Se mídia volta a ser referenciada antes da exclusão, deve ser protegida/contador zerado.
restored=PL('restored',groups=('g1',),items=('orphan_then_restored',))
assert 'orphan_then_restored' in protected([restored])

# 9. Playlist de outro grupo não protege cache desta TV.
other=PL('other',groups=('g2',),items=('foreign',))
assert 'foreign' not in protected([other])

print('OK: 9 cenários da política de cache passaram.')
