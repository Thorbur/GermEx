import datetime
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from bs4 import BeautifulSoup
import random
import re
from urllib.parse import quote


FEED = "https://www.tagesschau.de/xml/atom/"

TEST_TEMPLATE = """
<html lang="de">
<head>
    <meta charset="UTF-8">
    <title>Deutschtest</title>
    <script>
        function evaluate_test() {
            let all_gaps = document.getElementsByClassName("fill_in");
            let correct = 0;
            for(const gap of all_gaps){
                let solution = gap.getAttribute("name");
                let entered = gap.value;
                if(solution === entered){
                    gap.style.backgroundColor = "lightgreen";
                    correct++;
                } else {
                    gap.style.backgroundColor = "tomato";
                    gap.title = solution;
                }
            }
            document.getElementById("result").innerHTML = "Ergebnis: " + correct/all_gaps.length*100 +"%% richtig.";
        }
    </script>
</head>
<body style="background-color: blanchedalmond;">
<div id="source">Artikelquelle: <a href="%s" target="_blank">%s</a></div>
<br>
<br>
<div id="text">
    <p>
        %s
    </p>
</div>
<div><br><br><button id="evaluate" onclick="evaluate_test()">Auswerten</button><br><br></div>
<div id="result"></div>
</body>
</html>
"""

GAP_TEMPLATE = """
    <input type="text" class="fill_in" style="width: 60px;" name="%s">
"""


class InvalidArticleException(Exception):
    pass


def get_random_article_link_from_feed(feed_url):
    html = urlopen(feed_url).read()
    soup = BeautifulSoup(html, "html.parser")

    entries = soup.find_all(name="entry")
    valid_article_urls = []
    for entry in entries:
        link = entry.find("link")
        article_url = link.attrs["href"]
        if "tagesschau.de" in article_url:
            valid_article_urls.append(article_url)

    if valid_article_urls:
        return valid_article_urls[random.randint(0, len(valid_article_urls) - 1)]
    else:
        return None


def get_article_text_from_url(article_url):
    html = urlopen(article_url).read()
    soup = BeautifulSoup(html, "html.parser")

    # kill all script and style elements
    for script in soup(["script", "style"]):
        script.extract()  # rip it out

    article = soup.find(name="div", attrs={"class": "section sectionZ sectionArticle"})
    if article:
        sections = article.find_all(name="p", attrs={"class": "text small"})

        # get text
        full_text = ""
        # print(sections)
        for section in sections:
            text = section.get_text()
            text = text.replace(r"<a[^>]*>", "").replace("</a>", "")

            # break into lines and remove leading and trailing space on each
            lines = (line.strip() for line in text.splitlines())
            # break multi-headlines into a line each
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            # drop blank lines
            text = '\n'.join(chunk for chunk in chunks if chunk)
            if text:
                text.replace("|", "").strip()
                full_text += " " + text

        return full_text.replace("|", "").replace("\n", "")
    else:
        raise InvalidArticleException(article_url)


DICT_LOOKUP_RESULTS = {}

DUDEN_SEARCH_URL = "https://www.duden.de/suchen/dudenonline/%s"
DUDEN_NOT_FOUND_MESSAGE = "liefert keine Ergebnisse"
TFD_SEARCH_URL = "https://de.thefreedictionary.com/%s"
TFD_NOT_FOUND_MESSAGE = "Das Wort konnte im Wörterbuch nicht gefunden werden"
DWDS_SEARCH_URL = "https://www.dwds.de/?q=%s"
DWDS_NOT_FOUND_MESSAGE = "ist nicht in unseren gegenwartssprachlichen lexikalischen Quellen vorhanden"
DICT_SEARCH_URL = DWDS_SEARCH_URL
DICT_NOT_FOUND_MESSAGE = DWDS_NOT_FOUND_MESSAGE


def is_word_in_dict(word):
    if word:
        if word in DICT_LOOKUP_RESULTS:
            return DICT_LOOKUP_RESULTS[word]
        else:
            print(word)
            try:
                html = urlopen(DICT_SEARCH_URL % quote(word)).read()
            except (HTTPError, URLError, TimeoutError):
                DICT_LOOKUP_RESULTS[word] = False
                return False
            result = DICT_NOT_FOUND_MESSAGE not in html.decode("UTF-8")
            DICT_LOOKUP_RESULTS[word] = result
            return result
    else:
        return None


def create_gap_word(word):
    if word:
        word, beginning, ending = get_plain_word(word)

        split_index = random.randint(len(word)//2, len(word)//2+1)
        return word[0:split_index] + beginning + GAP_TEMPLATE % word[split_index: len(word)] + ending
    else:
        return None


def get_plain_word(word):
    beginning = ""
    ending = ""
    while len(word) > 0 and word[0] in ["'", '"', "("]:
        beginning += word
        word = word[1:]
    while len(word) > 0 and word[-1] in [".", ",", "?", "!", '"', ":", ";", "'", ")"]:
        ending = word[-1] + ending
        word = word[:-1]
    return word, beginning, ending


def generate_test(link, text):
    html_text = ""

    # sentence by sentence
    # each create gaps in 1-2 randomly selected words
    # glue everything together
    sentences = []
    parts = text.strip().split(". ")
    for pn, part in enumerate(parts):
        if "?" in part or "!" in part:
            part_indices = [m.start() for m in re.finditer('[?!]', part)]
            last_index = 0
            for index in part_indices:
                sentences.append(part[last_index:index+1])
                last_index = index + 1
            if len(part) > last_index:
                sentences.append(part[last_index:len(part)])
        elif pn < len(parts) - 1:
            sentences.append(part + ". ")

    for sn, sentence in enumerate(sentences):
        sentence_words = sentence.split(" ")
        possible_test_words = []
        for w in range(0, len(sentence_words)):
            word = sentence_words[w]
            if word and len(word) > 2:
                if word[0].islower() or (word.istitle() and is_word_in_dict(get_plain_word(word)[0])):
                    possible_test_words.append(w)

        if possible_test_words:
            for _ in range(0, random.randint(1, 2 if len(possible_test_words) > 1 else 1)):
                selected_for_gap = possible_test_words[random.randint(0, len(possible_test_words)-1)]
                sentence_words[selected_for_gap] = create_gap_word(sentence_words[selected_for_gap])
                possible_test_words.remove(selected_for_gap)

        for w, word in enumerate(sentence_words):
            # no need for space in first sentence + word
            if sn == 0 and w == 0:
                html_text += word
            else:
                html_text += " " + word

    return TEST_TEMPLATE % (link, link, html_text)


def save_test(file_path, test):
    with open(file_path, "w+") as out_file:
        out_file.write(test)


def main():
    # TODO: add command line args
    article_link = get_random_article_link_from_feed(FEED)
    article_text = get_article_text_from_url(article_link)
    # TODO: add article url to output
    test = generate_test(article_link, article_text)
    save_test("deutschtest_%s.html" % datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S"), test)


if __name__ == "__main__":
    main()
