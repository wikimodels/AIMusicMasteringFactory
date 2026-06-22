import re

with open('index.html', 'r', encoding='utf-8') as f:
    text = f.read()

# The truncated snippet we want to replace
target = """      document.body.innerHTML = '<div style="display:flex; align-items:center; just
  renderSearch();

});



document.getElementById('btn-close-search').addEventListener('click', () => {"""

replacement = """      document.body.innerHTML = '<div style="display:flex; align-items:center; justify-content:center; height:100vh; color:#fff;"><h1>Server Stopped</h1></div>';
    } catch(e) {}
  }
});

const searchOverlay = document.getElementById('search-overlay');
const searchInput = document.getElementById('search-input');
const searchResults = document.getElementById('search-results');

document.getElementById('btn-search').addEventListener('click', () => {
  searchOverlay.classList.add('open');
  searchInput.value = '';
  renderSearch();
});

document.getElementById('btn-close-search').addEventListener('click', () => {"""

new_text = text.replace(target, replacement)

# Check if there is another variation
if new_text == text:
    # try regex
    target_re = re.compile(r"      document\.body\.innerHTML = '<div style=\"display:flex; align-items:center; just\n\s*renderSearch\(\);\n\n\}\);\n\n\n\ndocument\.getElementById\('btn-close-search'\)\.addEventListener\('click', \(\) => \{")
    new_text = target_re.sub(replacement, text)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(new_text)
print("Done")
