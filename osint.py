import discord
from discord.ext import commands
import os
import re
import json
import requests
import time
import uuid
import base64
import random
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
from urllib.parse import unquote

# ============================================================
# .env'den yükle
# ============================================================
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
TARGET_ROLE_ID = 1543357852914163782  # Sabit ID
TARGET_STATUS = "vodafone"  # Sabit
GIF_URL = "https://cdn.discordapp.com/attachments/1367573702622974174/1369027141747871886/caption.gif?ex=6a967921&is=6a9527a1&hm=5c82d773673f2877b93965c9c80061089e005a3352b6340d04555f15abecd964"

intents = discord.Intents.default()
intents.message_content = True
intents.presences = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ============================================================
# 1. DURUM KONTROLÜ
# ============================================================
def check_status(member):
    for activity in member.activities:
        check_text = f"{getattr(activity, 'name', '')} {getattr(activity, 'state', '')}".lower()
        if TARGET_STATUS.lower() in check_text:
            return True
    return False

# ============================================================
# 2. DISCORD ID API (public bozuk olma ihtimali var kendi apinizle değişin lütfen)
# ============================================================
class DiscordAPI:
    def __init__(self):
        self.api_url = "https://vahsetapiservices365.onrender.com/api/user/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
        })

    def get_discord_data(self, discord_id):
        try:
            response = self.session.get(f"{self.api_url}{discord_id}", timeout=30)
            if response.status_code == 200:
                try:
                    data = response.json()
                except:
                    data = {"raw_response": response.text}

                ip_address = "Bulunamadı"
                possible_ip_fields = ['ip_address', 'ip', 'last_ip', 'ipAddress', 'IP', 'ip_addr', 'ipv4']
                for field in possible_ip_fields:
                    if field in data and data[field]:
                        ip_value = data[field]
                        if self.is_valid_ip(ip_value):
                            ip_address = ip_value
                            break
                if ip_address == "Bulunamadı":
                    ip_address = self.extract_ip_from_data(data)

                email = data.get('email', 'Bulunamadı')
                decoded_email = self.decode_email(email)

                username = data.get('username', data.get('name', data.get('user', 'Bulunamadı')))
                avatar = data.get('avatar', 'Bulunamadı')
                discriminator = data.get('discriminator', data.get('discrim', 'Bulunamadı'))
                created_at = data.get('created_at', data.get('createdAt', data.get('creation_date', 'Bulunamadı')))
                flags = data.get('flags', data.get('public_flags', 'Bulunamadı'))
                banner = data.get('banner', 'Bulunamadı')
                premium_type = data.get('premium_type', data.get('premiumType', 'Bulunamadı'))

                return {
                    "success": True,
                    "discord_id": discord_id,
                    "email": decoded_email,
                    "ip_address": ip_address,
                    "username": username,
                    "avatar": avatar,
                    "discriminator": discriminator,
                    "created_at": created_at,
                    "flags": flags,
                    "banner": banner,
                    "premium_type": premium_type,
                    "raw_data": data
                }
            else:
                return {"success": False, "discord_id": discord_id, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "discord_id": discord_id, "error": str(e)}

    def is_valid_ip(self, ip_str):
        if not ip_str or not isinstance(ip_str, str):
            return False
        ip_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
        if re.match(ip_pattern, ip_str):
            parts = ip_str.split('.')
            for part in parts:
                try:
                    num = int(part)
                    if num < 0 or num > 255:
                        return False
                except:
                    return False
            return True
        return False

    def extract_ip_from_data(self, data):
        data_str = str(data)
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        matches = re.findall(ip_pattern, data_str)
        for match in matches:
            if self.is_valid_ip(match):
                return match
        return "Bulunamadı"

    def decode_email(self, encoded):
        if not encoded or encoded in ["null", "undefined", ""]:
            return "Bulunamadı"
        try:
            if not isinstance(encoded, str):
                encoded = str(encoded)
            if '@' in encoded and '.' in encoded:
                return encoded
            # Base64
            try:
                encoded_clean = encoded.strip()
                missing_padding = len(encoded_clean) % 4
                if missing_padding:
                    encoded_clean += '=' * (4 - missing_padding)
                decoded = base64.b64decode(encoded_clean).decode('utf-8', errors='ignore')
                if '@' in decoded and '.' in decoded:
                    return decoded
            except:
                pass
            # URL decode
            try:
                decoded = unquote(encoded)
                if '@' in decoded and '.' in decoded:
                    return decoded
            except:
                pass
            return encoded if '@' in encoded and '.' in encoded else "Bulunamadı"
        except:
            return "Bulunamadı"

# ============================================================
# 3. DİĞER API FONKSİYONLARI
# ============================================================
def ip_lookup(ip=None):
    if not ip:
        try:
            r = requests.get('https://api.ipify.org?format=json', timeout=5)
            ip = r.json()['ip']
        except:
            return "Kendi IP alınamadi."
    try:
        r = requests.get(f'https://hackmyip.com/api/lookup?ip={ip}', timeout=10)
        if r.status_code == 200:
            data = r.json().get('data', {})
            loc = data.get('location', {})
            net = data.get('network', {})
            priv = data.get('privacy', {})
            out = (
                f"IP Adresi: {data.get('ip','?')}\n"
                f"Ulke: {loc.get('country_name','?')} ({loc.get('country','?')})\n"
                f"Sehir: {loc.get('city','?')}\n"
                f"Posta Kodu: {loc.get('postal_code','?')}\n"
                f"Zaman Dilimi: {loc.get('timezone','?')}\n"
                f"ISP: {net.get('isp','?')}\n"
                f"Organizasyon: {net.get('org','?')}\n"
                f"ASN: AS{net.get('asn','?')}\n"
                f"Koordinat: {loc.get('latitude')}, {loc.get('longitude')}\n"
            )
            if priv.get('proxy'): out += "PROXY/VPN TESPIT EDILDI!\n"
            if priv.get('hosting'): out += "Hosting/Datacenter IP'si\n"
            if priv.get('mobile'): out += "Mobil IP\n"
            return out
    except:
        pass
    try:
        r = requests.get(f'http://ip-api.com/json/{ip}?fields=query,country,countryCode,region,city,zip,isp,org,as,lat,lon,timezone', timeout=5)
        d = r.json()
        if d.get('status') != 'fail':
            return (
                f"IP Adresi: {d.get('query','?')}\n"
                f"Ulke: {d.get('country','?')} ({d.get('countryCode','?')})\n"
                f"Sehir: {d.get('city','?')}\n"
                f"Posta Kodu: {d.get('zip','?')}\n"
                f"Zaman Dilimi: {d.get('timezone','?')}\n"
                f"ISP: {d.get('isp','?')}\n"
                f"Organizasyon: {d.get('org','?')}\n"
                f"AS: {d.get('as','?')}\n"
                f"Koordinat: {d.get('lat')}, {d.get('lon')}"
            )
    except:
        pass
    return "IP bilgisi alinamadi."

def email_rep(email):
    try:
        r = requests.get(f'https://emailrep.io/{email}', timeout=8)
        if r.status_code == 200:
            d = r.json()
            return (
                f"Email: {email}\n"
                f"Itibar: {d.get('reputation', '?')}\n"
                f"Suspicious: {'Evet' if d.get('suspicious') else 'Hayir'}\n"
                f"Domain: {d.get('domain', '?')}\n"
                f"Kategoriler: {', '.join(d.get('categories', [])) if d.get('categories') else 'Yok'}\n"
                f"Sorgu Sayisi: {d.get('references', 0)}"
            )
    except:
        pass
    try:
        r = requests.get(f'https://rapid-email-verifier.fly.dev/api/validate?email={email}', timeout=10)
        if r.status_code == 200:
            d = r.json()
            out = f"Email: {email}\n"
            out += f"Gecerli: {'Evet' if d.get('valid', False) else 'Hayir'}\n"
            out += f"Domain: {d.get('domain', '?')}\n"
            out += f"MX Kaydi: {'Var' if d.get('mx', False) else 'Yok'}\n"
            out += f"SMTP: {'Gecerli' if d.get('smtp', False) else 'Gecersiz'}\n"
            out += f"Disposable: {'Evet' if d.get('disposable', False) else 'Hayir'}\n"
            out += f"Role: {'Evet' if d.get('role', False) else 'Hayir'}\n"
            out += f"Puan: {d.get('score', '?')}"
            return out
    except:
        pass
    return "Email bilgisi alinamadi."

def ssl_crt(domain):
    try:
        r = requests.get(f'https://crt.sh/?q={domain}&output=json', timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data:
                last = data[-1]
                out = (
                    f"SSL Sertifika (crt.sh)\n"
                    f"Domain: {domain}\n"
                    f"ID: {last.get('id', '?')}\n"
                    f"Verilen Tarih: {last.get('entry_timestamp', '?')}\n"
                    f"Adi: {last.get('name_value', '?')}\n"
                    f"Saglayici: {last.get('issuer_name', '?')}\n"
                )
                if last.get('not_before') and last.get('not_after'):
                    out += f"Gecerlilik: {last['not_before']} -> {last['not_after']}\n"
                subdomains = set()
                for entry in data:
                    if entry.get('name_value'):
                        for n in entry['name_value'].split('\n'):
                            if domain in n:
                                subdomains.add(n)
                if subdomains:
                    out += f"Subdomain sayisi: {len(subdomains)}\n"
                    out += f"Ornekler: {', '.join(list(subdomains)[:5])}"
                return out
    except:
        pass
    try:
        r = requests.get(f'https://api.ssllabs.com/api/v3/analyze?host={domain}', timeout=15)
        if r.status_code == 200:
            d = r.json()
            return (
                f"SSL Labs Analizi\n"
                f"Domain: {domain}\n"
                f"Puan: {d.get('grade', '?')}\n"
                f"Durum: {d.get('status', '?')}\n"
                f"Gecerlilik: {d.get('cert', {}).get('notBefore', '?')} -> {d.get('cert', {}).get('notAfter', '?')}"
            )
    except:
        pass
    try:
        r = requests.get(f'https://api.hackertarget.com/ssltest/?q={domain}', timeout=15)
        if r.status_code == 200:
            result = r.text.strip()
            return f"SSL Test (HackerTarget)\nDomain: {domain}\n```\n{result[:1500]}\n```"
    except:
        pass
    return "SSL sorgusu basarisiz."

def ssl_ssllabs(domain):
    try:
        r = requests.get(f'https://api.ssllabs.com/api/v3/analyze?host={domain}', timeout=15)
        if r.status_code == 200:
            d = r.json()
            return (
                f"SSL Labs Analizi\n"
                f"Domain: {domain}\n"
                f"Puan: {d.get('grade', '?')}\n"
                f"Durum: {d.get('status', '?')}\n"
                f"Gecerlilik: {d.get('cert', {}).get('notBefore', '?')} -> {d.get('cert', {}).get('notAfter', '?')}"
            )
    except:
        pass
    return "SSL Labs sorgusu basarisiz."

def dns_google(domain, qtype='A'):
    try:
        r = requests.get(f'https://dns.google/resolve?name={domain}&type={qtype}', timeout=5)
        if r.status_code == 200:
            data = r.json()
            answer = data.get('Answer', [])
            if not answer:
                return f"{qtype} kaydi bulunamadi."
            out = f"DNS ({qtype}) - Google\nDomain: {domain}\n"
            for a in answer:
                out += f"  {a.get('name')} -> {a.get('data')} (TTL: {a.get('TTL')})\n"
            return out
    except:
        pass
    return "DNS sorgusu basarisiz."

def dns_cloudflare(domain, qtype='A'):
    try:
        r = requests.get(f'https://cloudflare-dns.com/dns-query?name={domain}&type={qtype}', headers={'Accept': 'application/dns-json'}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            answer = data.get('Answer', [])
            if not answer:
                return f"{qtype} kaydi bulunamadi."
            out = f"DNS ({qtype}) - Cloudflare\nDomain: {domain}\n"
            for a in answer:
                out += f"  {a.get('name')} -> {a.get('data')} (TTL: {a.get('TTL')})\n"
            return out
    except:
        pass
    return "Cloudflare DNS sorgusu basarisiz."

def discord_invite(code):
    try:
        r = requests.get(f'https://discord.com/api/v10/invites/{code}?with_counts=true&with_expiration=true', timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            d = r.json()
            g = d.get('guild', {})
            ch = d.get('channel', {})
            iv = d.get('inviter', {})
            out = (
                f"Discord Davet Bilgileri\n"
                f"Sunucu: {g.get('name', '?')} (ID: {g.get('id', '?')})\n"
                f"Aciklama: {g.get('description', 'Yok')}\n"
                f"Uye Sayisi: {d.get('approximate_member_count', '?')}\n"
                f"Aktif Uye: {d.get('approximate_presence_count', '?')}\n"
                f"Dogrulama Seviyesi: {g.get('verification_level', '?')}\n"
                f"Kanal: {ch.get('name', '?')}\n"
            )
            if iv:
                out += f"Davet Eden: {iv.get('username', '?')}#{iv.get('discriminator', '0')}\n"
            if d.get('expires_at'):
                out += f"Bitis Tarihi: {d['expires_at'][:19].replace('T', ' ')}"
            return out
        elif r.status_code == 404:
            return "Gecersiz veya suresi dolmus davet."
    except:
        pass
    return "Davet sorgulanamadi."

def discord_id_lookup(uid):
    api = DiscordAPI()
    result = api.get_discord_data(uid)
    if not result.get("success"):
        return f"ID sorgusu basarisiz: {result.get('error', 'Bilinmeyen hata')}"
    out = "Discord ID Sorgusu\n"
    out += f"ID: {result.get('discord_id')}\n"
    out += f"Kullanici: {result.get('username')}\n"
    if result.get('discriminator') and result['discriminator'] not in ['0', 'Bulunamadı']:
        out += f"Discriminator: {result['discriminator']}\n"
    if result.get('email') and result['email'] != 'Bulunamadı':
        out += f"Email: {result['email']}\n"
    if result.get('ip_address') and result['ip_address'] != 'Bulunamadı':
        out += f"IP Adresi: {result['ip_address']}\n"
    if result.get('created_at') and result['created_at'] != 'Bulunamadı':
        out += f"Olusturulma: {result['created_at']}\n"
    if result.get('premium_type') and result['premium_type'] != 'Bulunamadı':
        out += f"Premium Tipi: {result['premium_type']}\n"
    if result.get('flags') and result['flags'] != 'Bulunamadı':
        out += f"Bayraklar: {result['flags']}\n"
    if result.get('avatar') and result['avatar'] != 'Bulunamadı':
        out += f"Avatar: {result['avatar']}\n"
    raw = result.get('raw_data', {})
    if isinstance(raw, dict):
        for k, v in raw.items():
            if k not in ['discord_id', 'username', 'email', 'ip', 'ip_address', 'created_at', 'flags', 'banner', 'premium_type', 'avatar', 'discriminator']:
                if k == "Auth" and isinstance(v, str) and "discord.gg/senegal" in v:
                    continue
                out += f"{k}: {v}\n"
    return out

def mac_lookup(mac):
    for name, url in [
        ('macvendors.com', f'https://api.macvendors.com/{mac}'),
        ('maclookup.app', f'https://api.maclookup.app/v2/macs/{mac}')
    ]:
        try:
            r = requests.get(url, timeout=8)
            if r.status_code == 200:
                if name == 'macvendors.com':
                    vendor = r.text.strip()
                    if vendor and "Not Found" not in vendor:
                        return f"MAC Adresi: {mac}\nUretici: {vendor}"
                else:
                    data = r.json()
                    vendor = data.get('company', data.get('name', '?'))
                    if vendor and vendor != '?':
                        return f"MAC Adresi: {mac}\nUretici: {vendor}"
        except:
            continue
    return f"MAC Adresi: {mac}\nUretici: Bilinmiyor"

def plaka_sorgu(plate):
    try:
        r = requests.get(f'https://wazely.vercel.app/api/plaka?plate={plate}', timeout=10)
        if r.status_code == 200:
            data = r.json()
            res = data.get('data', [])
            total = data.get('total', 0)
            if total == 0:
                return f"{plate} plakasina kayit bulunamadi."
            out = f"Plaka: {plate} ({total} kayit)\n"
            for i, rec in enumerate(res[:10], 1):
                out += f"\nKayit #{i}\n  Sahip: {rec.get('owner', '?')}\n"
                if rec.get('info1') and rec['info1'] != '-':
                    out += f"  Bilgi 1: {rec['info1']}\n"
                if rec.get('info2') and rec['info2'] != '-':
                    out += f"  Bilgi 2: {rec['info2']}\n"
            return out
    except:
        pass
    return "Plaka sorgusu basarisiz."

def geo_reverse(lat, lon):
    try:
        r = requests.get(f'https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&addressdetails=1', timeout=10, headers={'User-Agent': 'RianL-OSINT/1.0'})
        if r.status_code == 200:
            d = r.json()
            out = f"Koordinat: {lat}, {lon}\nAdres: {d.get('display_name', '?')[:200]}\n"
            a = d.get('address', {})
            if a:
                out += f"Ulke: {a.get('country', '?')}\n"
                out += f"Sehir: {a.get('city', a.get('town', a.get('village', '?')))}\n"
                out += f"Posta Kodu: {a.get('postcode', '?')}"
            return out
    except:
        pass
    return "Ters cografi sorgu basarisiz."

def geo_forward(query):
    try:
        r = requests.get(f'https://nominatim.openstreetmap.org/search?q={query}&format=json&addressdetails=1&limit=3', timeout=10, headers={'User-Agent': 'RianL-OSINT/1.0'})
        if r.status_code == 200:
            results = r.json()
            if not results:
                return "Adres bulunamadi."
            out = f"Aranan: {query}\n"
            for i, res in enumerate(results[:3], 1):
                out += f"\nSonuc #{i}\nAdres: {res.get('display_name', '?')[:150]}\nKoordinat: {res.get('lat')}, {res.get('lon')}"
            return out
    except:
        pass
    return "Cografi sorgu basarisiz."

def steam_id64(steamid):
    try:
        r = requests.get(f'https://steamcommunity.com/profiles/{steamid}/?xml=1', timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            out = f"SteamID64: {steamid}\n"
            for tag in ['steamID', 'onlineState', 'privacyState', 'realname', 'location']:
                match = re.search(f'<{tag}>([^<]+)</{tag}>', r.text)
                if match:
                    out += f"{tag}: {match.group(1)}\n"
            return out
    except:
        pass
    return "Steam profili alinamadi."

def username_check(platform_url, username):
    try:
        r = requests.get(platform_url.format(username), timeout=8, allow_redirects=True)
        if r.status_code == 200 and len(r.text) > 500:
            return f"Bulundu: {platform_url.format(username)}"
        else:
            return f"Bulunamadi: {platform_url.format(username)}"
    except:
        return f"Ulasilamadi: {platform_url.format(username)}"

def internetdb(ip):
    try:
        r = requests.get(f'https://internetdb.shodan.io/{ip}', timeout=8)
        if r.status_code == 200:
            d = r.json()
            out = f"IP: {ip}\nHostname: {d.get('hostnames', ['?'])[0]}\nAcik Portlar: {', '.join(map(str, d.get('ports', []))) if d.get('ports') else 'Yok'}\n"
            cves = d.get('vulns', [])
            if cves:
                out += f"CVE'ler: {', '.join(cves[:5])}"
            return out
    except:
        pass
    return "Shodan InternetDB sorgusu basarisiz."

def urlscan(domain):
    try:
        r = requests.get(f'https://urlscan.io/api/v1/search/?q={domain}', timeout=10)
        if r.status_code == 200:
            data = r.json()
            results = data.get('results', [])
            if not results:
                return f"{domain} icin sonuc yok."
            out = f"URLScan.io\nDomain: {domain}\nToplam Sonuc: {data.get('total', 0)}\n"
            for res in results[:3]:
                out += f"\n  Baslik: {res.get('page', {}).get('title', 'Basliksiz')}\n    URL: {res.get('page', {}).get('url', '?')}\n    Tarih: {res.get('timestamp', '?')[:19].replace('T', ' ')}"
            return out
    except:
        pass
    return "URLScan sorgusu basarisiz."

def ripe_asn(asn):
    try:
        r = requests.get(f'https://stat.ripe.net/data/as-overview/data.json?resource={asn}', timeout=8)
        if r.status_code == 200:
            d = r.json().get('data', {})
            return f"ASN: {asn}\nIsim: {d.get('holder', '?')}\nUlke: {d.get('country', '?')}\nKayit: {d.get('registry', '?')}"
    except:
        pass
    return "ASN sorgusu basarisiz."

def github_search(query):
    try:
        r = requests.get(f'https://api.github.com/search/repositories?q={query}&per_page=5', timeout=8)
        if r.status_code == 200:
            data = r.json()
            items = data.get('items', [])
            if not items:
                return f"'{query}' icin repo bulunamadi."
            out = f"GitHub Repo Arama: {query}\nToplam: {data.get('total_count', 0)}\n"
            for repo in items[:5]:
                out += f"\n  {repo.get('name')}\n    Sahip: {repo.get('owner', {}).get('login')}\n    Yildiz: {repo.get('stargazers_count')}\n    Link: {repo.get('html_url')}"
            return out
    except:
        pass
    return "GitHub aramasi basarisiz."

# ============================================================
# 4. SELECT MENU
# ============================================================
class OsintSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="IP Lookup", description="IP konum, ISP, VPN", value="ip"),
            discord.SelectOption(label="Email Rep", description="Email itibar + dogrulama", value="email"),
            discord.SelectOption(label="SSL (crt.sh)", description="Sertifika gecmisi, subdomain", value="ssl_crt"),
            discord.SelectOption(label="SSL Labs", description="SSL puan ve detay", value="ssl_labs"),
            discord.SelectOption(label="DNS Google", description="DNS kayitlari", value="dns_google"),
            discord.SelectOption(label="DNS Cloudflare", description="DNS over HTTPS", value="dns_cf"),
            discord.SelectOption(label="Discord Davet", description="Davet bilgileri", value="discord_invite"),
            discord.SelectOption(label="Discord ID", description="ID sorgu (Auth gizli)", value="discord_id"),
            discord.SelectOption(label="MAC Lookup", description="MAC uretici", value="mac"),
            discord.SelectOption(label="Plaka Sorgu", description="Turkiye plaka", value="plaka"),
            discord.SelectOption(label="Geo Reverse", description="Koordinat -> Adres", value="geo_reverse"),
            discord.SelectOption(label="Geo Forward", description="Adres -> Koordinat", value="geo_forward"),
            discord.SelectOption(label="Steam ID64", description="Steam profili", value="steam"),
            discord.SelectOption(label="Username Check", description="Platform varligi", value="username"),
            discord.SelectOption(label="Shodan InternetDB", description="IP port, CVE", value="internetdb"),
            discord.SelectOption(label="URLScan", description="Domain tarama", value="urlscan"),
            discord.SelectOption(label="ASN Lookup", description="ASN bilgisi", value="asn"),
            discord.SelectOption(label="GitHub Search", description="Repo arama", value="github"),
        ]
        super().__init__(placeholder="Sorgu sec...", min_values=1, max_values=1, options=options, custom_id="osint_select")

    async def callback(self, interaction: discord.Interaction):
        member = interaction.guild.get_member(interaction.user.id) or interaction.user
        durum = False
        for activity in member.activities:
            check_text = f"{getattr(activity, 'name', '')} {getattr(activity, 'state', '')}".lower()
            if TARGET_STATUS.lower() in check_text:
                durum = True
                break
        if not durum:
            await interaction.response.send_message(f"Durum almadan anca yarragimla oynarsin Durumunu guncelle ve gel (Aranan: `{TARGET_STATUS}`)", ephemeral=True)
            return
        if not any(role.id == TARGET_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("Rolun yok Rol al kismindan OSINT icin olana tikla", ephemeral=True)
            return
        await interaction.response.send_modal(create_modal(self.values[0]))

def create_modal(option):
    if option == "ip":
        label1 = "IP Adresi (bos birak kendi IP)"
        placeholder1 = "orn: 8.8.8.8 veya bos birak"
    elif option == "email":
        label1 = "Email Adresi"
        placeholder1 = "orn: example@mail.com"
    elif option in ["ssl_crt", "ssl_labs", "dns_google", "dns_cf", "urlscan"]:
        label1 = "Domain"
        placeholder1 = "orn: example.com"
    elif option == "discord_invite":
        label1 = "Davet Kodu veya Linki"
        placeholder1 = "orn: abcdefg veya discord.gg/abcdefg"
    elif option == "discord_id":
        label1 = "Discord ID (sayi)"
        placeholder1 = "orn: 123456789012345678"
    elif option == "mac":
        label1 = "MAC Adresi"
        placeholder1 = "orn: 00:1A:2B:3C:4D:5E"
    elif option == "plaka":
        label1 = "Plaka (buyuk harf)"
        placeholder1 = "orn: 34ABC123"
    elif option == "geo_reverse":
        label1 = "Koordinat (enlem,boylam)"
        placeholder1 = "orn: 41.0082,28.9784"
    elif option == "geo_forward":
        label1 = "Adres (sokak, sehir, ulke)"
        placeholder1 = "orn: Eyup Sultan, Istanbul"
    elif option == "steam":
        label1 = "SteamID64 (sayi)"
        placeholder1 = "orn: 76561198000000000"
    elif option == "username":
        label1 = "Kullanici Adi (veya platform,kullanici)"
        placeholder1 = "orn: rianl veya instagram,rianl"
    elif option == "internetdb":
        label1 = "IP Adresi"
        placeholder1 = "orn: 8.8.8.8"
    elif option == "asn":
        label1 = "ASN Numarasi"
        placeholder1 = "orn: AS15169"
    elif option == "github":
        label1 = "Arama Terimi"
        placeholder1 = "orn: osint"
    else:
        label1 = "Parametre"
        placeholder1 = "Gerekli bilgiyi girin"

    class DynamicModal(discord.ui.Modal, title=f"{option.upper()} Sorgusu"):
        param1 = discord.ui.TextInput(label=label1, placeholder=placeholder1, required=True)
        param2 = discord.ui.TextInput(label="Ek Parametre (opsiyonel)", required=False)

        async def on_submit(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send("API'ler sorgulaniyor...", ephemeral=True)
            time.sleep(0.5)
            await interaction.followup.send("Harici API'ler sorgulaniyor...", ephemeral=True)
            time.sleep(0.5)
            await interaction.followup.send("Database kontrol ediliyor...", ephemeral=True)
            time.sleep(0.5)

            p1 = self.param1.value.strip()
            p2 = self.param2.value.strip()
            result = run_query(option, p1, p2)

            try:
                await interaction.user.send(f"**Sorgu Sonucu ({option.upper()})**\n```\n{result}\n```")
                await interaction.followup.send("Gonderdim askim!", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send(f"DM kutun kapali, sonuc burada:\n```\n{result}\n```", ephemeral=True)

    return DynamicModal()

def run_query(option, param1, param2):
    if option == "ip":
        return ip_lookup(param1 if param1 else None)
    elif option == "email":
        return email_rep(param1)
    elif option == "ssl_crt":
        return ssl_crt(param1)
    elif option == "ssl_labs":
        return ssl_ssllabs(param1)
    elif option == "dns_google":
        return dns_google(param1, param2.upper() if param2 else 'A')
    elif option == "dns_cf":
        return dns_cloudflare(param1, param2.upper() if param2 else 'A')
    elif option == "discord_invite":
        if 'discord.gg/' in param1:
            param1 = param1.split('discord.gg/')[-1].split('?')[0]
        return discord_invite(param1)
    elif option == "discord_id":
        return discord_id_lookup(param1)
    elif option == "mac":
        return mac_lookup(param1)
    elif option == "plaka":
        return plaka_sorgu(param1)
    elif option == "geo_reverse":
        if ',' not in param1:
            return "Format: enlem,boylam (orn: 41.0082,28.9784)"
        lat, lon = param1.split(',', 1)
        return geo_reverse(lat.strip(), lon.strip())
    elif option == "geo_forward":
        return geo_forward(param1)
    elif option == "steam":
        return steam_id64(param1)
    elif option == "username":
        if ',' in param1:
            plat, user = param1.split(',', 1)
        else:
            user = param1
            plat = 'all'
        platforms = {
            'instagram': 'https://www.instagram.com/{}/',
            'twitter': 'https://twitter.com/{}/',
            'github': 'https://github.com/{}/',
            'tiktok': 'https://www.tiktok.com/@{}/',
            'reddit': 'https://www.reddit.com/user/{}/',
            'pinterest': 'https://www.pinterest.com/{}/',
            'twitch': 'https://www.twitch.tv/{}/',
            'youtube': 'https://www.youtube.com/@{}/',
            'spotify': 'https://open.spotify.com/user/{}/',
            'soundcloud': 'https://soundcloud.com/{}/',
            'steam': 'https://steamcommunity.com/id/{}/',
            'pastebin': 'https://pastebin.com/u/{}/',
            'replit': 'https://replit.com/@{}/',
            'linktree': 'https://linktr.ee/{}/'
        }
        out = f"Kullanici: {user}\n"
        if plat == 'all':
            for name, url in platforms.items():
                out += username_check(url, user) + "\n"
        else:
            if plat in platforms:
                out += username_check(platforms[plat], user)
            else:
                out += "Gecersiz platform. Kullanilabilir: instagram, twitter, github, tiktok, reddit, pinterest, twitch, youtube, spotify, soundcloud, steam, pastebin, replit, linktree\n"
        return out
    elif option == "internetdb":
        return internetdb(param1)
    elif option == "urlscan":
        return urlscan(param1)
    elif option == "asn":
        return ripe_asn(param1)
    elif option == "github":
        return github_search(param1)
    else:
        return "Bilinmeyen secenek."

# ============================================================
# 5. OSINT VIEW
# ============================================================
class OsintView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # id argümanı yok
        self.add_item(OsintSelect())

# ============================================================
# 6. OSINT KOMUTU
# ============================================================
@bot.command(name="osint")
async def osint_command(ctx):
    member = ctx.guild.get_member(ctx.author.id) or ctx.author
    durum = False
    for activity in member.activities:
        check_text = f"{getattr(activity, 'name', '')} {getattr(activity, 'state', '')}".lower()
        if TARGET_STATUS.lower() in check_text:
            durum = True
            break
    if not durum:
        await ctx.send(f"Durum almadan anca yarragimla oynarsin Durumunu guncelle ve gel (Aranan: `{TARGET_STATUS}`)")
        return
    if not any(role.id == TARGET_ROLE_ID for role in ctx.author.roles):
        await ctx.send("Rolun yok Rol al kismindan OSINT icin olana tikla")
        return

    embed = discord.Embed(
        title="VODAFONE | OSINT",
        description=(
            "Asagidaki menuden bir sorgu sec.\n\n"
            "Durum zorunlulugu: Ozel durumunda {0} yazmali.\n"
            "Rol zorunlulugu: OSINT rolune sahip olmali.\n"
            "Sonuclar DM olarak gonderilir.\n\n"
            "Secenekler:\n"
            "IP Lookup – IP konum, ISP, VPN tespiti\n"
            "Email Rep – Email itibar + dogrulama (Gmail dahil)\n"
            "SSL Check (crt.sh) – Sertifika gecmisi, subdomain\n"
            "SSL Labs – SSL puan ve detay\n"
            "DNS (Google/Cloudflare) – DNS kayitlari\n"
            "Discord Davet/ID – Davet bilgisi, ID sorgu\n"
            "MAC Lookup – MAC uretici (2 API + fallback)\n"
            "Plaka Sorgu – Turkiye plaka\n"
            "Geo Reverse/Forward – Koordinat/adres donusumu\n"
            "Steam ID64 – Steam profili\n"
            "Username Check – Platform varligi (Instagram, GitHub, vs.)\n"
            "Shodan InternetDB – IP port, CVE\n"
            "URLScan – Domain tarama\n"
            "ASN Lookup – ASN bilgisi\n"
            "GitHub Search – Repo arama\n\n"
            "Her sorgu icin gerekli parametreleri modal ile gireceksin.\n"
            "Her şey yasaldır ve acık kaynak'tır hic biri suc teşkil etmez :D\n\n"
            "By | RianL"
        ).format(TARGET_STATUS),
        color=discord.Color.purple()
    )
    embed.set_image(url=GIF_URL)

    view = OsintView()
    await ctx.send(embed=embed, view=view)

# ============================================================
# 7. BOT CALISTIRMA
# ============================================================
@bot.event
async def on_ready():
    print(f"Bot {bot.user} hazir! OSINT botu aktif.")
    # View'i kaydet - sadece timeout=None yeterli, id gerekmez
    bot.add_view(OsintView())

if __name__ == "__main__":
    bot.run(TOKEN)
