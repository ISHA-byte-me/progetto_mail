# script per svuotare la casella email dalla monnezza
# legge i domini da account_trovati.txt e sposta nel cestino tutte le email di quei mittenti
# cerca anche per parole chiave tipo newsletter, unsubscribe, offerta, ecc.
# ATTENZIONE: questo script modifica la tua email, sposta le mail nel cestino
#             le mail nel cestino vengono eliminate dopo 30 giorni automaticamente
#             oppure puoi svuotare il cestino manualmente

# per farlo funzionare:
# 1. stessa cartella di trova_account.py e client_secret.json
# 2. python pulisci_email.py

import os
import re
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# questo script ha bisogno di permessi di modifica (non solo lettura)
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# parole chiave extra per trovare altra monnezza oltre ai domini
EXTRA_QUERIES = [
    # newsletter e disiscrizioni
    'unsubscribe',
    'subject:"newsletter"',

    # promozioni e offerte
    'subject:"offerta" OR subject:"promozione" OR subject:"sconto"',
    'subject:"offer" OR subject:"promotion" OR subject:"discount" OR subject:"deal"',
    'subject:"sale" OR subject:"coupon" OR subject:"codice sconto"',

    # spedizioni e ordini
    'subject:"spedizione" OR subject:"spedito" OR subject:"in consegna"',
    'subject:"tracking" OR subject:"traccia" OR subject:"pacco"',
    'subject:"ordine confermato" OR subject:"ordine spedito" OR subject:"ordine consegnato"',
    'subject:"your order" OR subject:"order confirmed" OR subject:"order shipped" OR subject:"order delivered"',
    'subject:"conferma ordine" OR subject:"riepilogo ordine"',

    # carta giovani merito
    'from:cartgiovaniemerito OR subject:"carta giovani merito" OR subject:"carta giovani"',

    # steam
    'from:noreply@steampowered.com OR from:support@steampowered.com OR from:noreply@steam.com',

    # gamestop
    'from:@gamestop.it OR from:@gamestop.com',

    # twitch
    'from:no-reply@twitch.tv OR from:@twitch.tv',

    # aggiornamenti generici
    'subject:"aggiornamento" OR subject:"update"',
]

MAX = 3000  # max email per query


def login_gmail():
    creds = None

    # usa un file token separato per non sovrascrivere quello di trova_account.py
    token_file = 'token_write.json'

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('client_secret.json'):
                print("errore: client_secret.json non trovato")
                exit(1)
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_file, 'w') as f:
            f.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


def leggi_domini(filepath='account_trovati.txt'):
    domini = []
    if not os.path.exists(filepath):
        print(f"file {filepath} non trovato, salto la pulizia per dominio")
        return domini

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            match = re.match(r'^([\w.\-]+\.\w+)\s+\(\d+', line.strip())
            if match:
                domini.append(match.group(1))

    print(f"domini letti da account_trovati.txt: {len(domini)}")
    return domini


def cerca_messaggi(service, query):
    messaggi = []
    try:
        result = service.users().messages().list(
            userId='me', q=query, maxResults=MAX
        ).execute()
        messaggi.extend(result.get('messages', []))

        while 'nextPageToken' in result:
            result = service.users().messages().list(
                userId='me', q=query,
                maxResults=MAX,
                pageToken=result['nextPageToken']
            ).execute()
            messaggi.extend(result.get('messages', []))

    except Exception as e:
        print(f"  errore nella ricerca: {e}")

    return messaggi


def sposta_nel_cestino(service, ids):
    if not ids:
        return

    batch_size = 1000
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i+batch_size]
        try:
            service.users().messages().batchModify(
                userId='me',
                body={
                    'ids': batch,
                    'addLabelIds': ['TRASH'],
                    'removeLabelIds': ['INBOX']
                }
            ).execute()
            print(f"  spostate {min(i+batch_size, len(ids))}/{len(ids)} email nel cestino...")
            time.sleep(0.5)
        except Exception as e:
            print(f"  errore: {e}")


def main():
    print("connessione a gmail...")
    gmail = login_gmail()
    print("connesso\n")

    print("ATTENZIONE: questo script spostera nel cestino tutte le email")
    print("dei siti in account_trovati.txt + email con parole chiave tipo newsletter.")
    print("Le email nel cestino vengono eliminate dopo 30 giorni.")
    print()
    conferma = input("vuoi continuare? (scrivi 'si' per confermare): ").strip().lower()
    if conferma != 'si':
        print("annullato")
        exit(0)

    print()
    tutti_gli_id = set()

    domini = leggi_domini()
    if domini:
        print("\ncerco email per dominio...\n")
        for domain in domini:
            query = f"from:@{domain}"
            print(f"  {domain}...", end=' ')
            msgs = cerca_messaggi(gmail, query)
            ids = [m['id'] for m in msgs]
            tutti_gli_id.update(ids)
            print(f"{len(ids)} email trovate")

    print("\ncerco altra monnezza per parole chiave...\n")
    for query in EXTRA_QUERIES:
        print(f"  query: {query[:50]}...", end=' ')
        msgs = cerca_messaggi(gmail, query)
        ids = [m['id'] for m in msgs]
        tutti_gli_id.update(ids)
        print(f"{len(ids)} email trovate")

    print(f"\ntotale email da eliminare: {len(tutti_gli_id)}")

    if len(tutti_gli_id) == 0:
        print("niente da eliminare")
        return

    conferma2 = input(f"confermi l'eliminazione di {len(tutti_gli_id)} email? (scrivi 'si'): ").strip().lower()
    if conferma2 != 'si':
        print("annullato")
        exit(0)

    print("\nelimino...")
    sposta_nel_cestino(gmail, list(tutti_gli_id))

    print(f"\nfatto! {len(tutti_gli_id)} email spostate nel cestino.")
    print("ricordati di svuotare il cestino su Gmail per liberare spazio.")


if __name__ == '__main__':
    main()