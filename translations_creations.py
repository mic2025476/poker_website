import polib
from googletrans import Translator

# Load the PO file
po = polib.pofile('locale/de/LC_MESSAGES/django.po')

translator = Translator()

for entry in po:
    # Skip empty entries or plural forms if already translated
    if not entry.msgid or entry.msgstr:
        continue
    # Translate each msgid to German
    translation = translator.translate(entry.msgid, src='en', dest='de')
    entry.msgstr = translation.text

# Save the updated PO file
po.save()
