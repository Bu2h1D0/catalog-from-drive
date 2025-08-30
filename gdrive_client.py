import os.path
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

def list_subfolders(service, parent_folder_id):
    """List all subfolders in a given parent folder."""
    print("Ricerca delle sottocartelle (prodotti)...")
    try:
        query = f"'{parent_folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name)', pageSize=100).execute()
        return results.get('files', [])
    except HttpError as error:
        print(f"Si è verificato un errore durante la lettura delle sottocartelle: {error}")
        return []

from jinja2 import Environment, FileSystemLoader
import re

def list_images_in_folder(service, folder_id):
    """List all image files in a given folder, fetching necessary links."""
    try:
        # Request thumbnailLink for previews and webViewLink for full-size images
        query = f"'{folder_id}' in parents and (mimeType='image/jpeg' or mimeType='image/png' or mimeType='image/webp') and trashed = false"
        results = service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, thumbnailLink, webViewLink)',
            pageSize=100
        ).execute()
        return results.get('files', [])
    except HttpError as error:
        print(f"Si è verificato un errore durante la lettura delle immagini: {error}")
        return []

def generate_site(products_data):
    """Generates the static HTML site from product data."""
    print("\nInizio la generazione del sito web statico...")
    # Setup Jinja2 environment
    env = Environment(loader=FileSystemLoader('templates'))

    # Create output directory if it doesn't exist
    os.makedirs("docs/products", exist_ok=True)

    # Render Index Page
    index_template = env.get_template('index.html')
    with open('docs/index.html', 'w', encoding='utf-8') as f:
        f.write(index_template.render(products=products_data))
    print("- Pagina `index.html` creata.")

    # Render Product Pages
    product_template = env.get_template('product.html')
    for product in products_data:
        with open(product['url'], 'w', encoding='utf-8') as f:
            f.write(product_template.render(product=product))
        print(f"- Pagina prodotto creata: {product['url']}")

    print("\nGenerazione del sito completata con successo!")
    print("Puoi trovare i file nella cartella 'docs'.")

def slugify(text):
    """Converts a string to a URL-friendly and ASCII-safe slug."""
    text = text.lower().strip()
    # Replace spaces and underscores with hyphens
    text = re.sub(r'[\s_]+', '-', text)
    # Remove any character that is not a standard ASCII letter, number, or hyphen
    text = re.sub(r'[^a-z0-9-]', '', text)
    # Remove leading/trailing hyphens that might have been created
    text = text.strip('-')
    return text

def main():
    """Main function to run the script."""
    # --- Authentication ---
    creds = None
    if not os.path.exists("token.json"):
        print("ERRORE: File 'token.json' non trovato. Esegui prima il flusso di autenticazione per generarlo.")
        sys.exit(1)

    try:
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    except Exception as e:
        print(f"ERRORE: Impossibile caricare le credenziali da token.json: {e}")
        sys.exit(1)

    if not creds or not creds.valid:
        print("ERRORE: Credenziali in token.json non valide o scadute. Rimuovi 'token.json' e riesegui per autenticarti di nuovo.")
        sys.exit(1)

    print("Autenticazione riuscita tramite token.json.")

    # --- Main Logic ---
    if len(sys.argv) < 2:
        print("\nERRORE: Manca l'ID della cartella principale.")
        print(f"Uso: python3 {sys.argv[0]} <ID_CARTELLA_PRODOTTI>")
        sys.exit(1)

    parent_folder_id = sys.argv[1]
    print(f"Utilizzo l'ID della cartella principale: {parent_folder_id}")

    try:
        service = build("drive", "v3", credentials=creds)
        product_folders = list_subfolders(service, parent_folder_id)

        if not product_folders:
            print(f"Nessuna sottocartella (prodotto) trovata nell'ID cartella fornito.")
            return

        print(f"Trovati {len(product_folders)} prodotti. Raccolta dati in corso...")

        products_data = []
        for folder in product_folders:
            images = list_images_in_folder(service, folder['id'])
            # Ensure images have webViewLink, some Drive files might not
            for img in images:
                if 'webViewLink' in img:
                    # The default webViewLink is a viewer, not a direct image link.
                    # We need to transform it to get a direct download link for embedding.
                    img['webViewLink'] = img['webViewLink'].replace('/view?usp=drivesdk', '/preview')

            slug = slugify(folder['name'])
            products_data.append({
                'id': folder['id'],
                'name': folder['name'],
                'images': images,
                'url': f'docs/products/{slug}.html'
            })

        generate_site(products_data)

    except HttpError as error:
        if error.resp.status == 404:
            print(f"\nERRORE 404: Impossibile trovare una cartella con l'ID fornito: '{parent_folder_id}'.")
            print("Verifica che l'ID sia corretto e di avere i permessi per visualizzare la cartella.")
        else:
            print(f"Si è verificato un errore durante l'interazione con l'API di Drive: {error}")
    except FileNotFoundError:
        print("\nERRORE: File 'credentials.json' non trovato!")
        print("Assicurati che il file sia presente nella stessa directory dello script.")

if __name__ == "__main__":
    main()
