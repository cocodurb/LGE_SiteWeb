import sys
import os

# Ajoute le dossier du site au path Python
sys.path.insert(0, os.path.dirname(__file__))

from server import app as application
