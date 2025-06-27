# IMPORT GŁÓWNEGO OBIEKTU APLIKACJI FLASK
from app import app

# IMPORTY BIBLIOTEK STANDARDOWYCH I ZEWNĘTRZNYCH
import os                                                                            # do operacji na plikach i folderach
import json                                                                          # do zapisu i odczytu danych w formacie JSON
import requests                                                                      # do wysyłania zapytań HTTP (np. pobieranie stron z Ceneo)
import pandas as pd                                                                  # do analizy i przetwarzania danych tabelarycznych
from bs4 import BeautifulSoup                                                        # do parsowania HTML i ekstrakcji danych ze stron
from matplotlib import pyplot as plt                                                 # do tworzenia wykresów (słupkowych, kołowych)
from flask import render_template, request, redirect, url_for, send_file, jsonify    # funkcje Flask do tworzenia widoków i obsługi HTTP
from app.config import headers                                                       # własny plik konfiguracyjny z nagłówkami HTTP
from app import utils                                                                # własny moduł z funkcjami pomocniczymi (np. extract_feature, selectors)
import io                                                                            # do tworzenia buforów danych (CSV, XLSX) w pamięci RAM
import matplotlib
matplotlib.use('Agg')                                                                # Ustawienie backendu Matplotlib na tryb bez interfejsu graficznego (dla serwera)

# STRONA GŁÓWNA APLIKACJI
@app.route("/")
def index():
    # wyświetla szablon strony głównej (index.html)
    return render_template("index.html")


# FORMULARZ DO WPROWADZENIA ID PRODUKTU
@app.route("/extract")
def display_form():
    # wyświetla formularz do wpisania ID produktu (extract.html)
    return render_template("extract.html")


# OBSŁUGA FORMULARZA I EKSTRAKCJA DANYCH O PRODUKCIE Z CENEO
@app.route("/extract", methods=["POST"])
def extract():
    # pobieramy ID produktu z formularza przesłanego metodą POST
    product_id = request.form.get('product_id')

    # budujemy URL do pierwszej strony z opiniami o produkcie
    next_page = f"https://www.ceneo.pl/{product_id}#tab=reviews"
    response = requests.get(next_page, headers=headers)

    # sprawdzamy, czy produkt istnieje i czy strona została poprawnie załadowana
    if response.status_code == 200:
        page_dom = BeautifulSoup(response.text, "html.parser")

        # pobieramy nazwę produktu oraz liczbę opinii (jeśli nie ma, zwracamy błąd)
        product_name = utils.extract_feature(page_dom, "h1")
        opinions_count = utils.extract_feature(page_dom, "a.product-review__link > span")

        if not opinions_count:
            # produkt istnieje, ale nie ma jeszcze opinii – informujemy użytkownika
            error = "Dla produktu o podanym id nie ma jeszcze żadnych opinii"
            return render_template("extract.html", error=error)
    else:
        # jeśli status nie jest 200, to strona nie istnieje (np. błędne ID)
        error = "Nie znaleziono produktu o podanym id"
        return render_template("extract.html", error=error)

    # inicjalizujemy listę na wszystkie opinie
    all_opinions = []

    # pętla pobierająca dane z kolejnych stron z opiniami
    while next_page:
        response = requests.get(next_page, headers=headers)
        if response.status_code == 200:
            page_dom = BeautifulSoup(response.text, "html.parser")
            # wybieramy tylko niepromowane opinie (bez user-post--highlight)
            opinions = page_dom.select("div.js_product-review:not(.user-post--highlight)")

            # ekstrakcja danych z każdej opinii na stronie
            for opinion in opinions:
                single_opinion = {
                    key: utils.extract_feature(opinion, *value)
                    for key, value in utils.selectors.items()
                }
                all_opinions.append(single_opinion)

            # próba znalezienia linku do kolejnej strony
            try:
                next_page = "https://www.ceneo.pl" + utils.extract_feature(page_dom, "a.pagination__next", "href")
            except TypeError:
                # jeśli nie znaleziono kolejnej strony – koniec pętli
                next_page = None
        else:
            break  # jeśli błąd w żądaniu HTTP, kończymy pobieranie

    # tworzymy katalogi (jeśli nie istnieją) na dane produktów i opinie
    os.makedirs("./app/data/opinions", exist_ok=True)
    os.makedirs("./app/data/products", exist_ok=True)

    # zapisujemy wszystkie opinie do pliku JSON
    with open(f"./app/data/opinions/{product_id}.json", "w", encoding="UTF-8") as jf:
        json.dump(all_opinions, jf, indent=4, ensure_ascii=False)

    # konwersja opinii na DataFrame do dalszej analizy
    opinions = pd.DataFrame.from_dict(all_opinions)
    # przetwarzamy dane: konwersja ocen gwiazdkowych i przydatności do float/int
    opinions.stars = opinions.stars.apply(lambda s: s.split("/")[0].replace(",", ".")).astype(float)
    opinions.useful = opinions.useful.astype(int)
    opinions.unuseful = opinions.unuseful.astype(int)

    # obliczamy podstawowe statystyki opisowe dotyczące opinii
    stats = {
        'product_id': product_id,
        'product_name': product_name,
        "opinions_count": opinions.shape[0],
        "pros_count": int(opinions.pros.astype(bool).sum()),
        "cons_count": int(opinions.cons.astype(bool).sum()),
        "pros_cons_count": int(opinions.apply(lambda o: bool(o.pros) and bool(o.cons), axis=1).sum()),
        "average_stars": float(opinions.stars.mean()),
        "pros": opinions.pros.explode().dropna().value_counts().to_dict(),
        "cons": opinions.cons.explode().dropna().value_counts().to_dict(),
        "recommendations": opinions.recommendation.value_counts(dropna=False).reindex(['Nie polecam', 'Polecam', None], fill_value=0).to_dict(),
    }

    # zapisujemy statystyki do osobnego pliku JSON
    with open(f"./app/data/products/{product_id}.json", "w", encoding="UTF-8") as jf:
        json.dump(stats, jf, indent=4, ensure_ascii=False)

    # przekierowanie do strony ze szczegółami produktu
    return redirect(url_for('product', product_id=product_id, product_name=product_name))


# STRONA Z LISTĄ WSZYSTKICH ZEBRANYCH PRODUKTÓW
@app.route("/products")
def products():
    # odczytujemy wszystkie pliki JSON ze statystykami produktów
    products_files = os.listdir("./app/data/products")
    products_list = []

    for filename in products_files:
        with open(f"./app/data/products/{filename}", "r", encoding="UTF-8") as jf:
            product = json.load(jf)
            products_list.append(product)

    # przekazujemy dane do szablonu products.html
    return render_template("products.html", products=products_list)


# STRONA Z INFORMACJAMI O AUTORZE APLIKACJI
@app.route("/author")
def author():
    # wyświetla szablon author.html
    return render_template("author.html")


# STRONA Z OPINIAMI O KONKRETNYM PRODUKCIE
@app.route("/product/<product_id>")
def product(product_id):
    # nazwa produktu przekazywana przez parametr GET (query string)
    product_name = request.args.get('product_name')

    # wczytanie opinii z pliku JSON
    with open(f"./app/data/opinions/{product_id}.json", "r", encoding="UTF-8") as jf:
        opinions = json.load(jf)

    # wyświetlenie szablonu z listą opinii
    return render_template("product.html", product_id=product_id, product_name=product_name, opinions=opinions)


# STRONA Z WYKRESAMI DOTYCZĄCYMI PRODUKTU
@app.route("/charts/<product_id>")
def charts(product_id):
    # upewniamy się, że katalog na wykresy istnieje
    os.makedirs("./app/static/images/charts", exist_ok=True)

    # wczytujemy dane statystyczne o produkcie
    with open(f"./app/data/products/{product_id}.json", "r", encoding="UTF-8") as jf:
        stats = json.load(jf)

    # tworzymy wykres kołowy dla rekomendacji (polecam, nie polecam, brak zdania)
    recommendations = pd.Series(stats['recommendations'])
    recommendations.plot.pie(
        label="",
        title=f"Rozkład rekomendacji w opiniach o produkcie {product_id}",
        labels=['Nie polecam', 'Polecam', "Nie mam zdania"],
        colors=["crimson", 'forestgreen', "lightgrey"],
        autopct="%1.1f%%"  # format procentowy na wykresie
    )
    plt.savefig(f"./app/static/images/charts/{stats['product_id']}_pie.png")
    plt.close()

    # tworzymy wykres słupkowy dla liczby ocen gwiazdkowych
    with open(f"./app/data/opinions/{product_id}.json", "r", encoding="UTF-8") as jf:
        opinions = pd.DataFrame(json.load(jf))
    opinions.stars = opinions.stars.apply(lambda s: float(s.split("/")[0].replace(",", ".")))

    # obliczamy liczbę opinii dla każdej liczby gwiazdek (np. 1.0, 2.0, itd.)
    stars_counts = opinions.stars.value_counts().sort_index()

    # konfigurujemy i rysujemy wykres
    plt.figure(figsize=(8,5))
    stars_counts.plot.bar(
        color="skyblue",
        title=f"Liczba opinii z poszczególnymi ocenami gwiazdkowymi dla produktu {product_id}"
    )
    plt.xlabel("Liczba gwiazdek")
    plt.ylabel("Liczba opinii")
    plt.xticks(rotation=0)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig(f"./app/static/images/charts/{stats['product_id']}_bar.png")
    plt.close()

    # wyświetlamy stronę z wykresami (charts.html)
    return render_template("charts.html", product_id=product_id, product_name=stats['product_name'])




# EKSPORT DANYCH DO PLIKÓW W WYBRANYM FORMACIE
@app.route('/export/<product_id>/<format>')
def export_product(product_id, format):
    # POBRANIE DANYCH Z PLIKU JSON
    data = get_product_data(product_id)
    if not data:
        return "Brak danych dla tego produktu", 404
        
    # KONWERSJA DANYCH Z FORMATU JSON (lista słowników) DO OBIEKTU DataFrame
    # (ułatwia to eksport danych do różnych formatów)
    df = pd.DataFrame(data)

    # EKSPORT DO CSV
    if format == 'csv':
        # tworzymy bufor tekstowy do zapisu danych CSV w pamięci RAM
        buffer = io.StringIO()
        # zapisujemy dane do bufora jako CSV, bez indeksu wierszy
        df.to_csv(buffer, index=False)
        buffer.seek(0)        # cofamy wskaźnik bufora na początek

        # przygotowujemy odpowiedź HTTP, która pozwoli użytkownikowi pobrać plik .csv
        return send_file(
            io.BytesIO(buffer.getvalue().encode()),        # konwersja z tekstu na bajty
            mimetype='text/csv',                           # typ MIME dla plików CSV
            as_attachment=True,                            # ustawia nagłówki Content-Disposition do pobierania
            download_name=f'product_{product_id}.csv'      # sugerowana nazwa pliku do pobrania
        )

    # EKSPORT DO XLSX
    elif format == 'xlsx':
        # tworzymy bufor binarny (BytesIO) do przechowywania pliku Excel
        buffer = io.BytesIO()

        # używamy ExcelWriter z silnikiem xlsxwriter do zapisu pliku Excel do bufora
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Opinie')         # zapis danych do arkusza "Opinie"
            writer.close()  # zamknięcie writer'a (jest istotne przy pracy z buforami binarnymi)
        buffer.seek(0)          # ustawiamy wskaźnik bufora na początek
        
        # zwracamy plik XLSX jako odpowiedź do pobrania
        return send_file(
            buffer,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'product_{product_id}.xlsx'
        )

    # EKSPORT DO JSON
    # elif format == 'json':
    #     return jsonify(data)        # automatycznie ustawia Content-Type na application/json
    
    elif format == 'json':
        return send_file(
            io.BytesIO(json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')),
            mimetype='application/json',
            as_attachment=True,
            download_name=f'product_{product_id}.json'
    )

    # OBSŁUGA NIEOBSŁUGIWANEGO FORMATU
    else:
        return "Unsupported format", 400         # kod HTTP 400 = Bad Request



# FUNKCJA POMOCNICZA - POBRANIE DANYCH O OPINIACH DLA PRODUKTU
# (przyjmuje ID produktu i zwraca listę opinii (słowników) jeśli plik istnieje, w przeciwnym razie zwraca pustą listę)
def get_product_data(product_id):
    file_path = f"./app/data/opinions/{product_id}.json"
    
    # sprawdzamy czy plik istnieje
    if os.path.exists(file_path):
        # jeśli tak, otwieramy i wczytujemy dane JSON jako listę słowników
        with open(file_path, "r", encoding="UTF-8") as jf:
            return json.load(jf)
    else:
        return []



