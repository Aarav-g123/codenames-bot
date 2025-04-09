from datamuse import datamuse
from functools import lru_cache
import string
import wikipediaapi
import requests

class CodenamesHelper:
    """Core engine for processing word associations and generating hints"""
    
    def __init__(self):
        self.datamuse = datamuse.Datamuse()
        self.datamuse.set_max_default(1000)
        self.wikipedia = wikipediaapi.Wikipedia(
            language='en',
            user_agent='CodenamesHelper/1.0'
        )
        self.common_words = {
            'i', 'a', 'an', 'the', 'and', 'but', 'or', 'to', 'of', 'in',
            'on', 'at', 'for', 'with', 'by', 'from', 'up', 'out', 'if', 'as'
        }

    def get_wikipedia_links(self, word):
        """Retrieve related terms from Wikipedia page links"""
        page = self.wikipedia.page(word)
        return list(page.links.keys()) if page.exists() else []

    @lru_cache(maxsize=100)
    def _query_datamuse(self, relation, word):
        """Generic method for Datamuse API queries with error handling"""
        try:
            results = self.datamuse.words(**{relation: word})
            return {item['word']: item['score'] for item in results}
        except requests.exceptions.RequestException:
            return {}

    def get_adjectives(self, word):
        """Fetch adjectives related to the given word"""
        return self._query_datamuse('rel_jja', word)

    def get_nouns(self, word):
        """Fetch nouns associated with the given word"""
        return self._query_datamuse('rel_jjb', word)

    def get_triggers(self, word):
        """Find words typically triggered by the given word"""
        return self._query_datamuse('rel_trg', word)

    def get_contextual(self, word):
        """Retrieve words appearing in similar contexts"""
        return self._query_datamuse('lc', word)

    def _normalize_scores(self, scores):
        """Normalize scores to 0-100 scale for comparison"""
        if not scores:
            return {}
        max_score = max(scores.values())
        min_score = min(scores.values())
        return {word: 100 * (score - min_score) / (max_score - min_score)
                for word, score in scores.items()}

    def _combine_data_sources(self, word):
        """Aggregate and weight data from multiple sources"""
        sources = [
            self.get_adjectives(word),
            self.get_nouns(word),
            self.get_triggers(word),
            self.get_contextual(word)
        ]
        combined = {}
        
        for source in sources:
            for term, score in self._normalize_scores(source).items():
                if ' ' not in term:
                    combined[term] = combined.get(term, 0) + score
        
        for term in self.get_wikipedia_links(word):
            if ' ' not in term:
                combined[term] = combined.get(term, 0) + 100
                
        return combined

    def find_common_associations(self, words):
        """Identify shared associations across multiple words"""
        word_data = [self._combine_data_sources(word) for word in words]
        common_terms = set.intersection(*[set(data) for data in word_data])
        
        return {
            term: sum(source[term] for source in word_data)
            for term in common_terms
            if term.lower() not in self.common_words
            and term.lower() not in map(str.lower, words)
            and term not in string.punctuation
        }

    def get_sorted_hints(self, associations):
        """Sort hints by descending score then alphabetical order"""
        return sorted(associations.items(), key=lambda x: (-x[1], x[0]))

class UserInterface:
    """Handles all user interactions and output formatting"""
    
    @staticmethod
    def get_words():
        """Collect words from user with validation"""
        words = []
        print("Enter at least 2 words (type 'done' when finished):")
        
        while len(words) < 2:
            word = input(f"Word {len(words)+1}: ").strip().lower()
            if word and word.isalpha():
                words.append(word)
        
        while True:
            word = input("Next word or 'done': ").strip().lower()
            if word == 'done':
                break
            if word and word.isalpha():
                words.append(word)
        
        return words

    @staticmethod
    def display_results(words, associations):
        """Display results in clean formatted output"""
        if not associations:
            print("\nNo valid hints found.")
            return
        
        print(f"\nTop hints for {', '.join(words)}:")
        for term, score in associations[:15]:
            print(f"  {term:<15} {score:.1f}")

def main():
    helper = CodenamesHelper()
    ui = UserInterface()
    
    target_words = ui.get_words()
    associations = helper.find_common_associations(target_words)
    sorted_hints = helper.get_sorted_hints(associations)
    
    ui.display_results(target_words, sorted_hints)

if __name__ == "__main__":
    main()