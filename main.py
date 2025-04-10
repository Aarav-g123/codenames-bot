import tkinter as tk
from tkinter import ttk, messagebox
from datamuse import datamuse
from functools import lru_cache
import string
import wikipediaapi
import requests
from collections import defaultdict

class CodenamesGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Codenames Spymaster Assistant")
        
        self.team_colors = {
            'Red': '#ff6666',
            'Blue': '#6666ff',
            'Neutral': '#ffff99',
            'Assassin': '#444444'
        }
        
        self.current_team = 'Red'
        self.word_grid = []
        self.game_words = []
        self.spymaster_team = 'Red'
        
        self.create_widgets()
        self.setup_grid()
        
    def create_widgets(self):
        self.control_frame = ttk.Frame(self.root)
        self.control_frame.pack(pady=10)
        
        self.team_selector = ttk.Combobox(self.control_frame, 
                                       values=['Red', 'Blue'],
                                       state='readonly')
        self.team_selector.set('Red')
        self.team_selector.pack(side=tk.LEFT, padx=5)
        
        self.generate_btn = ttk.Button(self.control_frame, text="Generate Clues",
                                     command=self.generate_clues)
        self.generate_btn.pack(side=tk.LEFT, padx=5)
        
        self.clue_frame = ttk.Frame(self.root)
        self.clue_frame.pack(pady=10)
        
        self.clue_listbox = tk.Listbox(self.clue_frame, height=10, width=30)
        self.clue_listbox.pack(side=tk.LEFT)
        
        self.grid_frame = ttk.Frame(self.root)
        self.grid_frame.pack(pady=10)

    def setup_grid(self):
        self.cells = []
        for row in range(5):
            row_cells = []
            for col in range(5):
                cell = tk.Button(self.grid_frame, text="", width=10, height=3,
                                command=lambda r=row, c=col: self.set_cell_team(r, c))
                cell.grid(row=row, column=col, padx=2, pady=2)
                row_cells.append(cell)
            self.cells.append(row_cells)
        
        self.load_words_popup()

    def load_words_popup(self):
        popup = tk.Toplevel()
        popup.title("Enter Codenames")
        
        tk.Label(popup, text="Enter 25 words (comma-separated):").pack(padx=10, pady=5)
        self.words_entry = tk.Text(popup, height=10, width=40)
        self.words_entry.pack(padx=10, pady=5)
        
        ttk.Button(popup, text="Load", command=lambda: self.process_words(popup)).pack(pady=5)

    def process_words(self, popup):
        try:
            words = self.words_entry.get(1.0, tk.END).strip().replace('\n', '').split(',')
            if len(words) != 25:
                messagebox.showerror("Error", "Please enter exactly 25 words")
                return
            
            self.game_words = [w.strip() for w in words]
            for row in range(5):
                for col in range(5):
                    self.cells[row][col].config(text=self.game_words[row*5 + col])
            popup.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Invalid input: {str(e)}")

    def set_cell_team(self, row, col):
        current_color = self.cells[row][col].cget('bg')
        teams = list(self.team_colors.keys())
        current_index = teams.index(self.current_team) if current_color == 'SystemButtonFace' else \
                       list(self.team_colors.values()).index(current_color)
        new_index = (current_index + 1) % len(self.team_colors)
        new_team = list(self.team_colors.keys())[new_index]
        
        self.cells[row][col].config(bg=self.team_colors[new_team])
        self.current_team = new_team

    def generate_clues(self):
        try:
            self.spymaster_team = self.team_selector.get()
            target_words = []
            avoid_words = []
            
            for row in range(5):
                for col in range(5):
                    word = self.game_words[row*5 + col]
                    cell_color = self.cells[row][col].cget('bg')
                    
                    if cell_color == self.team_colors[self.spymaster_team]:
                        target_words.append(word)
                    elif cell_color != self.team_colors['Neutral']:
                        avoid_words.append(word)
            
            if not target_words:
                messagebox.showwarning("Warning", "No target words selected!")
                return
            
            helper = CodenamesHelper()
            associations = helper.find_common_associations(target_words, avoid_words)
            sorted_hints = helper.get_sorted_hints(associations)
            
            self.clue_listbox.delete(0, tk.END)
            print("\nTOP CLUES DEBUG:")  # Debug header
            for hint_data in sorted_hints[:15]:
                count = hint_data['count']
                score = hint_data['score']
                word = hint_data['word']
                connected_words = ", ".join(sorted(hint_data['connected_words']))
                
                # Console debug output
                print(f"Clue: {word} ({score:.1f}) | Links {count} words: {connected_words}")
                
                # GUI display
                self.clue_listbox.insert(tk.END, f"{count} - {word} ({score:.1f})")
                
            if not sorted_hints:
                messagebox.showinfo("Info", "No valid clues found. Try different word combinations.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate clues: {str(e)}")

class CodenamesHelper:
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
        self.min_word_frequency = 2.0
        self.min_connection_count = 2

    def get_wikipedia_links(self, word):
        page = self.wikipedia.page(word)
        return list(page.links.keys()) if page.exists() else []

    @lru_cache(maxsize=100)
    def _query_datamuse(self, relation, word):
        try:
            results = self.datamuse.words(
                **{relation: word},
                md='f'
            )
            return {
                item['word']: {
                    'score': item['score'],
                    'freq': float(item.get('tags', ['0'])[0].split(':')[-1]),
                    'pos': item.get('tags', [''])[-1].split(':')[-1]
                }
                for item in results
                if 'tags' in item and len(item['tags']) >= 2
            }
        except Exception as e:
            return {}

    def get_adjectives(self, word):
        return self._query_datamuse('rel_jja', word)

    def get_nouns(self, word):
        return self._query_datamuse('rel_jjb', word)

    def get_triggers(self, word):
        return self._query_datamuse('rel_trg', word)

    def get_contextual(self, word):
        return self._query_datamuse('lc', word)
    def _is_valid_term(self, term, target_words):
        term_lower = term.lower()

        return (
            len(term) > 3 and  
            term_lower not in self.common_words and
            not any(c in term for c in string.punctuation) and
            not any(t.lower() in term_lower for t in target_words) and  
            not any(term_lower in t.lower() for t in target_words)
        )
    
    def _normalize_scores(self, scores):
        if not scores:
            return {}
        scores_list = list(scores.values())
        max_score = max(scores_list) if scores_list else 1
        min_score = min(scores_list) if scores_list else 0
        return {k: 100 * (v - min_score) / (max_score - min_score) if (max_score - min_score) != 0 else 50
                for k, v in scores.items()}

    def _combine_data_sources(self, word):
        sources = [
            self.get_adjectives(word),
            self.get_nouns(word),
            self.get_triggers(word),
            self.get_contextual(word)
        ]
        
        combined = defaultdict(float)
        wiki_terms = self.get_wikipedia_links(word)
        
        for source in sources:
            for term, data in source.items():
                if not self._is_valid_term(term, [word]):
                    continue

                if data['freq'] < self.min_word_frequency:
                    continue
                if data['pos'] not in ('adj', 'n'):
                    continue

                weight = 1.0
                if data['pos'] == 'adj':
                    weight *= 1.2 
                if term in wiki_terms:
                    weight *= 1.5  
                
                combined[term] += data['score'] * weight

        for term in wiki_terms:
            if self._is_valid_term(term, [word]):
                combined[term] += 80 

        return combined

    def find_common_associations(self, target_words, avoid_words):
        connection_map = defaultdict(lambda: {
            'words': set(),
            'scores': defaultdict(float),
            'total_score': 0
        })
        
        for target_word in target_words:
            word_associations = self._combine_data_sources(target_word)
            for term, score in word_associations.items():
                term_lower = term.lower()
                if (term_lower in {w.lower() for w in target_words} or
                    term_lower in {w.lower() for w in avoid_words}):
                    continue
                
                connection_map[term]['words'].add(target_word)
                connection_map[term]['scores'][target_word] = score
                connection_map[term]['total_score'] += score

        filtered = {}
        for term, data in connection_map.items():
            if (len(data['words']) >= self.min_connection_count and
                self._is_valid_term(term, target_words)):

                base_score = data['total_score']
                count_boost = len(data['words']) * 50
                final_score = base_score + count_boost
                
                filtered[term] = {
                    'count': len(data['words']),
                    'score': final_score,
                    'words': data['words'],
                    'breakdown': dict(data['scores'])
                }

        return filtered

    def get_sorted_hints(self, associations):
        def sort_key(item):
            term = item[0]
            data = item[1]
            return (-data['count'], -data['score'], term)
        
        sorted_terms = sorted(associations.items(), key=sort_key)
        return [
            {
                'word': term,
                'count': data['count'],
                'score': data['score'],
                'connected_words': list(data['words']) 
            }
            for term, data in sorted_terms
        ]

if __name__ == "__main__":
    root = tk.Tk()
    app = CodenamesGUI(root)
    root.mainloop()