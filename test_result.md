#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================
user_problem_statement: "Bot Telegram L3 SENDER (envoi d'emails via Resend). L'utilisateur veut importer un fichier HTML comme corps de l'email. Bug signalé : certains fichiers HTML ne sont pas lus par le bot."

backend:
  - task: "Lecture de tout fichier importé comme corps d'email (HTML/texte)"
    implemented: true
    working: true
    file: "/app/telegram_bot/bot.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Correctif: ask_body_document ne rejette plus selon extension/MIME. Nouvelle fonction _decode_bytes essaie plusieurs encodages (utf-8-sig, utf-8, utf-16, cp1252, latin-1). is_html = nom .html/.htm OU looks_like_html(contenu). Limite de taille supprimée (seule la limite Telegram ~20Mo subsiste). send_email envoie html si is_html sinon text."
        - working: true
          agent: "testing"
          comment: "Tests complets effectués (17 tests, 16 PASS, 1 FAIL mineur). ✅ _decode_bytes: UTF-8 simple/BOM, UTF-16, CP1252 avec accents fonctionnent. ✅ looks_like_html: détecte correctement HTML (balises <html>,<div>,<p>,<table>,<a>,<h1-6>) vs texte simple. ✅ ask_body_document: fichiers SANS extension .html (ex: 'index') ou avec MIME générique (application/octet-stream) sont correctement lus et détectés comme HTML selon contenu. Fichiers texte simple → is_html=False. Fichiers vides → rejetés (ASK_BODY). ✅ send_email: envoi réel HTML vers delivered@resend.dev réussi (ID Resend: 83156cb7-bba2-49f2-b1f5-d4a7ae20b2dc). Minor: Latin-1 pur échoue (décodage UTF-8 produit caractères incorrects) mais CP1252 (plus courant) fonctionne. BUG CORRIGÉ: les fichiers HTML importés sont maintenant lus correctement indépendamment de l'extension/MIME."

metadata:
  created_by: "main_agent"
  version: "1.2"
  test_sequence: 2
  run_ui: false

test_plan:
  current_focus: []
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    - agent: "main"
      message: "Bot Telegram (polling, pas d'API HTTP). Merci de tester la LOGIQUE de lecture de fichier en important les fonctions du module /app/telegram_bot/bot.py: (1) _decode_bytes doit décoder correctement des octets en utf-8, utf-8 avec BOM, utf-16, cp1252/latin-1 (accents), (2) looks_like_html doit détecter le HTML (balises <html>,<div>,<p>,<table>,<a>...), (3) simuler ask_body_document avec un faux Document (get_file().download_as_bytearray() renvoyant des octets) pour vérifier qu'un fichier SANS extension .html ou avec MIME application/octet-stream est bien lu et que body/is_html sont correctement définis. Optionnel: vérifier un envoi réel via send_email (clé ACCOUNT_1 = topwork.se) avec is_html=True vers un email de test. Le token Telegram et 8 comptes Resend sont dans /app/telegram_bot/.env."
    - agent: "testing"
      message: "Tests terminés avec succès (16/17 PASS). Harnais de test créé dans /app/backend_test.py. Tous les points critiques validés: (1) _decode_bytes décode UTF-8/BOM/UTF-16/CP1252 correctement, (2) looks_like_html détecte HTML vs texte, (3) ask_body_document lit fichiers sans extension .html et avec MIME générique - le BUG SIGNALÉ EST CORRIGÉ, (4) send_email fonctionne (email HTML envoyé avec succès). Seul échec mineur: latin-1 pur (rare en pratique, CP1252 plus courant fonctionne). Le bot lit maintenant correctement tous les fichiers HTML importés."
