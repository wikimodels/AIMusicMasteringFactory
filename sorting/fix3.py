import re

with open('index.html', 'r', encoding='utf-8') as f:
    text = f.read()

replacement = """          xhr.addEventListener('load', () => {
            if (xhr.status === 200) {
              const data = JSON.parse(xhr.responseText);
              const res = data.results && data.results[0];
              if (res && res.success) {
                progFill.style.width = '100%';
                progFill.style.background = 'var(--success)';
                statusEl.textContent = '✓';
                statusEl.style.color = 'var(--success)';
                itemEl.classList.add('success');
                successCount++;
                resolve();
              } else {
                reject(new Error(res ? res.error : 'Unknown error'));
              }
            } else {
              reject(new Error('HTTP ' + xhr.status));
            }
          });

          xhr.addEventListener('error', () => reject(new Error('Network error')));
          
          const formData = new FormData();
          formData.append('files[]', f);
          xhr.send(formData);
        });
      } catch (err) {
        errorCount++;
        progFill.style.background = 'var(--c-disliked)';
        statusEl.textContent = '✗';
        statusEl.style.color = 'var(--c-disliked)';
        itemEl.classList.add('error');
      }
    }

    btnBrowse.disabled = false;
    btnClear.disabled = false;

    if (errorCount === 0) {
      summary.textContent = `All ${successCount} files uploaded`;
      summary.className = 'upload-summary done';
      btnStart.style.display = 'none';
      loadTracks();
    } else {
      summary.textContent = `Uploaded ${successCount}, failed ${errorCount}`;
      summary.className = 'upload-summary';
      btnStart.disabled = false;
    }
  });

  updateActions();
})();"""

idx = text.find("itemEl.classList.add('success');")
idx2 = text.find("document.getElementById('btn-power-off').addEventListener('click', async () => {")

if idx != -1 and idx2 != -1:
    # We want to replace from `xhr.addEventListener('load'` to `})();`
    # Let's find the start
    start_idx = text.rfind("xhr.addEventListener('load'", 0, idx)
    new_text = text[:start_idx] + replacement + '\n\n' + text[idx2:]
    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(new_text)
    print("SUCCESS")
else:
    print(idx, idx2)
