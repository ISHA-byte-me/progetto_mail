# script per trovare tutti i siti dove mi sono registrato con la mia email
# usa la gmail api per cercare le email di registrazione
# alla fine salva tutto in un file txt con i link per cancellarsi

# per farlo funzionare:
# 1. pip install google-auth google-auth-oauthlib google-api-python-client
# 2. crea un progetto su console.cloud.google.com, abilita la gmail api
#    e scarica le credenziali oauth come "client_secret.json" nella stessa cartella
# 3. python trova_account.py

import os
import re
from collections import defaultdict

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# solo lettura, non tocca niente nella mail
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# parole chiave che di solito si trovano nelle mail di registrazione
queries = [
    'subject:"welcome" OR subject:"benvenuto" OR subject:"benvenuti"',
    'subject:"confirm your email" OR subject:"conferma email" OR subject:"verifica email"',
    'subject:"verify your email" OR subject:"verifica il tuo"',
    'subject:"account created" OR subject:"account creato"',
    'subject:"grazie per la registrazione" OR subject:"thank you for registering"',
    'subject:"completa la registrazione" OR subject:"complete your registration"',
    'subject:"activate your account" OR subject:"attiva il tuo account"',
]

MAX = 200  # quante mail cercare per ogni query


def login_gmail():
    creds = None

    # se ho gia fatto il login in precedenza riusa il token
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('client_secret.json'):
                print("errore: file client_secret.json non trovato")
                print("scaricalo dalla google cloud console e mettilo qui")
                exit(1)
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open('token.json', 'w') as f:
            f.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


def get_domain(email):
    # prendo il dominio dall'indirizzo email e tolgo i sottodomini tipo "mail." o "noreply."
    match = re.search(r'@([\w.\-]+)', email)
    if not match:
        return None
    domain = match.group(1)
    parts = domain.split('.')
    if len(parts) > 2:
        domain = '.'.join(parts[-2:])
    return domain


def get_mittente(headers):
    for h in headers:
        if h['name'].lower() == 'from':
            val = h['value']
            m = re.search(r'<(.+?)>', val)
            email = m.group(1) if m else val.strip()
            return email, get_domain(email)
    return None, None


def cerca(service, query):
    try:
        res = service.users().messages().list(userId='me', q=query, maxResults=MAX).execute()
        return res.get('messages', [])
    except Exception as e:
        print(f"errore: {e}")
        return []


def get_headers(service, msg_id):
    try:
        msg = service.users().messages().get(
            userId='me', id=msg_id, format='metadata',
            metadataHeaders=['From', 'Subject']
        ).execute()
        return msg.get('payload', {}).get('headers', [])
    except Exception:
        return []


def link_justdeleteme(domain):
    name = domain.split('.')[0]
    return f"https://justdeleteme.xyz/#{name}"


def main():
    print("connessione a gmail...")
    gmail = login_gmail()
    print("connesso\n")

    domini = defaultdict(lambda: {'count': 0, 'senders': set()})
    visti = set()

    print("cerco le email di registrazione...\n")

    for q in queries:
        print(f"  query: {q[:60]}...")
        messaggi = cerca(gmail, q)
        print(f"  trovati: {len(messaggi)}\n")

        for msg in messaggi:
            mid = msg['id']
            if mid in visti:
                continue
            visti.add(mid)

            headers = get_headers(gmail, mid)
            email, domain = get_mittente(headers)

            if domain:
                domini[domain]['count'] += 1
                if email:
                    domini[domain]['senders'].add(email)

    # ordino per numero di email ricevute
    risultati = sorted(domini.items(), key=lambda x: x[1]['count'], reverse=True)

    print(f"\n{'='*50}")
    print(f"siti trovati: {len(risultati)}")
    print(f"{'='*50}\n")

    righe = [f"siti trovati: {len(risultati)}\n", "=" * 50 + "\n\n"]

    for domain, info in risultati:
        link = link_justdeleteme(domain)
        print(f"  {domain} ({info['count']} email)")
        print(f"    cancellati qui: {link}\n")

        righe.append(f"{domain} ({info['count']} email)\n")
        righe.append(f"  JustDeleteMe: {link}\n")
        if info['senders']:
            righe.append(f"  mittente: {', '.join(list(info['senders'])[:2])}\n")
        righe.append("\n")

    with open('account_trovati.txt', 'w', encoding='utf-8') as f:
        f.writelines(righe)

    print("lista salvata in account_trovati.txt")


if __name__ == '__main__':
    main()