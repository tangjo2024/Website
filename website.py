import streamlit as st
import requests
from bs4 import BeautifulSoup
import collections
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
import concurrent.futures

# Initialize the Porter Stemmer
stemmer = PorterStemmer()

class WordsParser:
    search_tags = ['p', 'div', 'span', 'a', 'h1', 'h2', 'h3', 'h4']

    def __init__(self):
        self.common_words = collections.Counter()
        self.summary_sentences = []

    def handle_data(self, data):
        if self.current_tag in self.search_tags:
            for word in data.strip().split():
                common_word = word.lower().translate(str.maketrans('', '', '.,:"'))

                if (
                        len(common_word) > 2 and
                        common_word not in stopwords.words('english') and
                        common_word[0].isalpha()
                ):
                    self.common_words[common_word] += 1

            # Collecting potential summary sentences from paragraphs and headers
            if self.current_tag in ['p', 'h1', 'h2', 'h3']:
                self.summary_sentences.append(data.strip())

def is_similar(word1, word2):
    return stemmer.stem(word1.lower()) == stemmer.stem(word2.lower())

def get_keywords_and_summary_from_url(url, query_words):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html = response.text

        words_parser = WordsParser()
        soup = BeautifulSoup(html, 'html.parser')

        # Limit the number of tags processed to avoid large data
        tags = soup.find_all(words_parser.search_tags, limit=100)

        for tag in tags:
            words_parser.current_tag = tag.name
            words_parser.handle_data(tag.get_text())

        # Exclude query words and similar words using stemming and case normalization
        for query_word in query_words:
            query_word_stem = stemmer.stem(query_word.lower())
            words_parser.common_words = {word: count for word, count in words_parser.common_words.items() if not is_similar(word, query_word)}

        return words_parser.common_words, words_parser.summary_sentences
    except requests.RequestException as e:
        st.error(f"Error accessing {url}: {e}")
        return None, None

def get_google_results_count(query):
    url = f"https://www.google.com/search?q={query}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        result_stats = soup.find(id='result-stats')

        if result_stats:
            count_text = result_stats.text.split()[1].replace(',', '')
            return int(count_text), soup.select('.tF2Cxc a')
        else:
            return None, None
    except requests.RequestException as e:
        st.error(f"Error: {e}")
        return None, None

def get_top_website(result_urls):
    if not result_urls:
        return None

    return result_urls[0]['href'] if result_urls[0] else None

def main():
    st.title('Web Scraper')
    st.sidebar.title('Options')

    # Input query
    query = st.text_input('Enter your search query', 'Alternate Suspension Program')

    # Sidebar options
    max_results = st.sidebar.slider('Max Results to Fetch', 5, 25, 10)

    # Run the main script when button is clicked
    if st.button('Run'):
        with st.spinner('Fetching results...'):
            results_count, result_urls = get_google_results_count(query)

        if results_count is not None:
            # Display top website
            top_website = get_top_website(result_urls)
            if top_website:
                st.subheader('Top Website:')
                st.write(top_website)

            # Collect keyword data and summaries from multiple sources
            keyword_data_list = []
            all_summary_sentences = []

            # Use concurrent requests to fetch multiple URLs in parallel
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_to_url = {executor.submit(get_keywords_and_summary_from_url, url['href'], query.split()): url for url in result_urls[:max_results]}
                for future in concurrent.futures.as_completed(future_to_url):
                    url = future_to_url[future]
                    try:
                        keywords, summaries = future.result()
                        if keywords is not None:
                            keyword_data_list.append(keywords)
                            all_summary_sentences.extend(summaries)
                    except Exception as e:
                        st.error(f"Error retrieving data from {url['href']}: {e}")

            # Aggregate keyword data
            keyword_data_aggregated = collections.Counter()
            for keyword_data in keyword_data_list:
                keyword_data_aggregated.update(keyword_data)

            # Find top 10 most common words
            top_words = keyword_data_aggregated.most_common(10)

            # Create data for the bar chart
            chart_data = {word: count for word, count in top_words}

            # Display bar chart
            st.subheader('Top 10 Most Frequent Words:')
            st.bar_chart(chart_data)

            # Combine summary sentences to form a coherent summary
            max_summary_sentences = 5  # Limit summary to 5 sentences
            summary = ' '.join(all_summary_sentences[:max_summary_sentences])

            # Display summary of the input term
            st.subheader('Summary:')
            if summary:
                st.write(summary)
            else:
                st.warning(f"Failed to generate summary for '{query}'.")

            # Display popularity/number of searches
            st.subheader('Popularity/Number of searches:')
            st.write(results_count)

        else:
            st.error("Failed to retrieve results count.")

if __name__ == "__main__":
    main()
