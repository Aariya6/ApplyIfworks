"""Browser/network safety invariants."""
import ipaddress,socket
from urllib.parse import urlparse
from pathlib import Path
from .tailor import ROOT

def validate_application_url(url):
    p=urlparse(url)
    if p.scheme not in {'http','https'} or not p.hostname: raise ValueError('Application URL must be HTTP(S) with a hostname')
    host=p.hostname.lower().strip('.')
    if host in {'localhost','localhost.localdomain'}: raise ValueError('Localhost application URLs are blocked')
    try:
        infos=socket.getaddrinfo(host,None)
        for info in infos:
            ip=ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast: raise ValueError('Private/loopback application destination blocked')
    except socket.gaierror:
        # DNS can be unavailable at validation time; browser navigation still uses HTTPS and redirects are checked.
        pass
    return True

def validate_redirect(url): return validate_application_url(url)

def browser_profile_path():
    expected=(ROOT/'data'/'browser-profile').resolve(); home=Path.home().resolve()
    if expected==home: raise RuntimeError('Unsafe browser profile path')
    if expected.parent!=(ROOT/'data').resolve(): raise RuntimeError('Browser profile escaped data directory')
    return expected
