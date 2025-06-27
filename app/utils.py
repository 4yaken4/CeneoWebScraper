# SŁOWNIK SELECTORS DEFINIUJE, JAK POBIERAĆ KONKRETNE DANE Z KAŻDEJ OPINII
# klucze to nazwy danych, a wartości to krotki:
# (CSS selector, atrybut HTML [opcjonalnie], czy wiele wartości [opcjonalnie])

selectors = {
    "opinion_id": (None, 'data-entry-id'),                                               # identyfikator opinii pobierany z atrybutu HTML
    "author": ("span.user-post__author-name",),                                          # autor opinii (tekst z elementu <span>)
    "recommendation": ("span.user-post__author-recomendation > em",),                    # rekomendacja: "Polecam" / "Nie polecam"
    "stars": ("span.user-post__score-count",),                                           # ocena w gwiazdkach, np. "4,5/5"
    "content": ("div.user-post__text",),                                                 # treść opinii (główna część tekstowa)
    "pros": ("div.review-feature__item--positive", None, True),                          # lista zalet – wiele elementów
    "cons": ("div.review-feature__item--negative", None, True),                          # lista wad – wiele elementów
    "useful": ("button.vote-yes > span",),                                               # liczba osób, które uznały opinię za przydatną
    "unuseful": ("button.vote-no > span",),                                              # liczba osób, które uznały opinię za nieprzydatną
    "post_date": ("span.user-post__published > time:nth-child(1)", 'datetime'),          # data wystawienia opinii (z atrybutu datetime)
    "purchase_date": ("span.user-post__published > time:nth-child(2)", 'datetime'),      # data zakupu produktu (jeśli podana)
}


# FUNKCJA UNIWERSALNA DO WYDOBYWANIA DANYCH Z HTML-A ZA POMOCĄ SELECTORA
# ancestor – obiekt BeautifulSoup (np. jedna opinia)
# selector – selektor CSS do wskazania elementu (opcjonalny)
# attribute – jeśli podany, to zamiast tekstu zostanie zwrócony atrybut HTML (np. href, datetime)
# multiple – czy zwrócić wiele wyników (lista), np. dla wielu zalet lub wad

def extract_feature(ancestor, selector=None, attribute=None, multiple=False):
    if selector:  # jeśli został podany selektor CSS
        if multiple:  # jeśli ma zwrócić wiele elementów (lista)
            if attribute:
                # zwraca listę wartości atrybutu dla każdego znalezionego tagu
                return [tag[attribute].strip() for tag in ancestor.select(selector)]
            # zwraca listę tekstów dla każdego tagu
            return [tag.text.strip() for tag in ancestor.select(selector)]
        
        if attribute:
            try:
                # zwraca jeden atrybut z pierwszego dopasowanego elementu
                return ancestor.select_one(selector)[attribute].strip()
            except TypeError:
                # np. gdy element nie istnieje lub brak atrybutu
                return None
        try:
            # zwraca tekst pierwszego dopasowanego elementu
            return ancestor.select_one(selector).text.strip()
        except AttributeError:
            # jeśli brak takiego elementu – zwraca None
            return None

    # jeśli nie podano selektora, ale podano atrybut – zwracamy ten atrybut z bieżącego elementu
    if attribute:
        return ancestor[attribute].strip()

    # w przeciwnym razie zwracamy sam tekst elementu
    return ancestor.text.strip()
