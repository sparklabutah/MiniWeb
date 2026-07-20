"""Expand translation (LinguaBridge) base data.

The translator ships with 30 history rows / 15 saved phrases / 5 glossaries /
5 users, which leaves the history, saved and glossaries pages nearly empty.
Adds deterministic (seeded) synthetic users, past translations (history),
saved phrases and glossaries, matching the site's existing conventions:
ASCII-only text, romanized ja/zh/ko/ar, literal formulaic translations,
glossary entries stored as a JSON list of {"source", "target"} objects.

The history and saved pages render an unbounded per-user list, so volume is
spread across many users and capped well under ~500 rows per user (the
default auto-login user id 1 gets ~120 history rows). New history rows are
dated OLDER than all existing rows (before 2026-06-20) so existing
newest-first orderings are unchanged. Languages table (config) is untouched.

Insert-only; inserted ids recorded under data/backups/ for rollback.

Usage: python scripts/expand_translation_data.py [--dry-run]
"""
import datetime
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
rng = random.Random(20260720)

# New history/saved rows all dated before the oldest existing row (2026-06-20).
HIST_START = datetime.datetime(2026, 1, 5, 7, 0, 0)
HIST_END = datetime.datetime(2026, 6, 19, 22, 0, 0)

# ---------------------------------------------------------------------------
# Phrase bank: english -> per-language literal translation (site convention:
# ASCII only, unaccented Romance, romanized ja/zh/ko/ar/vi).
# ---------------------------------------------------------------------------
PHRASES = [
    ("Hello, how are you?", {
        "es": "Hola, como estas?", "fr": "Bonjour, comment allez-vous?",
        "de": "Hallo, wie geht es dir?", "it": "Ciao, come stai?",
        "pt": "Ola, como esta voce?", "ja": "konnichiwa, ogenki desu ka?",
        "zh": "ni hao ma?", "ko": "annyeonghaseyo, jal jinaeseyo?",
        "ar": "marhaban, kayfa haluk?", "vi": "Xin chao, ban khoe khong?"}),
    ("Good morning", {
        "es": "Buenos dias", "fr": "Bonjour", "de": "Guten Morgen",
        "it": "Buongiorno", "pt": "Bom dia", "ja": "ohayou gozaimasu",
        "zh": "zaoshang hao", "ko": "joeun achim", "ar": "sabah alkhayr",
        "vi": "Chao buoi sang"}),
    ("Good night", {
        "es": "Buenas noches", "fr": "Bonne nuit", "de": "Gute Nacht",
        "it": "Buona notte", "pt": "Boa noite", "ja": "oyasumi nasai",
        "zh": "wan an", "ko": "annyeonghi jumuseyo", "ar": "tusbih ala khayr",
        "vi": "Chuc ngu ngon"}),
    ("Thank you very much", {
        "es": "Muchas gracias", "fr": "Merci beaucoup", "de": "Danke sehr viel",
        "it": "Grazie mille", "pt": "Muito obrigado", "ja": "doumo arigatou",
        "zh": "feichang ganxie", "ko": "daedanhi gamsahamnida",
        "ar": "shukran jazilan", "vi": "Cam on rat nhieu"}),
    ("You are welcome", {
        "es": "De nada", "fr": "De rien", "de": "Gern geschehen",
        "it": "Prego", "pt": "De nada", "ja": "dou itashimashite",
        "zh": "bu keqi", "ko": "cheonmaneyo", "ar": "afwan",
        "vi": "Khong co gi"}),
    ("Where is the restaurant?", {
        "es": "Donde esta el restaurante?", "fr": "Ou est le restaurant?",
        "de": "Wo ist das Restaurant?", "it": "Dove e il ristorante?",
        "pt": "Onde fica o restaurante?", "ja": "resutoran wa doko desu ka?",
        "zh": "canting zai nali?", "ko": "sikdang eodi issoyo?",
        "ar": "ayna almataam?", "vi": "Nha hang o dau?"}),
    ("Where is the train station?", {
        "es": "Donde esta la estacion de tren?", "fr": "Ou est la gare?",
        "de": "Wo ist der Bahnhof?", "it": "Dove e la stazione?",
        "pt": "Onde fica a estacao de trem?", "ja": "eki wa doko desu ka?",
        "zh": "huochezhan zai nali?", "ko": "gichayeok eodi issoyo?",
        "ar": "ayna mahattat alqitar?", "vi": "Ga tau o dau?"}),
    ("How much does it cost?", {
        "es": "Cuanto cuesta?", "fr": "Combien ca coute?",
        "de": "Wie viel kostet das?", "it": "Quanto costa?",
        "pt": "Quanto custa?", "ja": "ikura desu ka?",
        "zh": "duoshao qian?", "ko": "eolmayeyo?",
        "ar": "kam althaman?", "vi": "Gia bao nhieu?"}),
    ("I need help please", {
        "es": "Necesito ayuda por favor", "fr": "J'ai besoin d'aide s'il vous plait",
        "de": "Ich brauche Hilfe bitte", "it": "Ho bisogno di aiuto per favore",
        "pt": "Preciso de ajuda por favor", "ja": "tasukete kudasai",
        "zh": "qing bang bang wo", "ko": "dowajuseyo",
        "ar": "ahtaj almusaeada min fadlik", "vi": "Toi can giup do"}),
    ("I do not understand", {
        "es": "No entiendo", "fr": "Je ne comprends pas",
        "de": "Ich verstehe nicht", "it": "Non capisco",
        "pt": "Nao entendo", "ja": "wakarimasen",
        "zh": "wo bu dong", "ko": "ihaega an dwaeyo",
        "ar": "la afham", "vi": "Toi khong hieu"}),
    ("Do you speak English?", {
        "es": "Hablas ingles?", "fr": "Parlez-vous anglais?",
        "de": "Sprechen Sie Englisch?", "it": "Parli inglese?",
        "pt": "Voce fala ingles?", "ja": "eigo wo hanasemasu ka?",
        "zh": "ni hui shuo yingyu ma?", "ko": "yeongeo hasil su isseoyo?",
        "ar": "hal tatakallam alingliziyya?", "vi": "Ban noi tieng Anh khong?"}),
    ("My name is Alex", {
        "es": "Me llamo Alex", "fr": "Je m'appelle Alex",
        "de": "Ich heisse Alex", "it": "Mi chiamo Alex",
        "pt": "Meu nome e Alex", "ja": "watashi no namae wa Alex desu",
        "zh": "wo jiao Alex", "ko": "je ireumeun Alex imnida",
        "ar": "ismi Alex", "vi": "Toi ten la Alex"}),
    ("See you tomorrow", {
        "es": "Hasta manana", "fr": "A demain", "de": "Bis morgen",
        "it": "A domani", "pt": "Ate amanha", "ja": "mata ashita",
        "zh": "mingtian jian", "ko": "naeil bwayo", "ar": "araka ghadan",
        "vi": "Hen gap lai ngay mai"}),
    ("The weather is good today", {
        "es": "El tiempo esta bueno hoy", "fr": "Il fait beau aujourd'hui",
        "de": "Das Wetter ist heute gut", "it": "Il tempo e bello oggi",
        "pt": "O tempo esta bom hoje", "ja": "kyou wa ii tenki desu",
        "zh": "jintian tianqi hen hao", "ko": "oneul nalssiga joayo",
        "ar": "altaqs jayid alyawm", "vi": "Hom nay troi dep"}),
    ("It is raining outside", {
        "es": "Esta lloviendo afuera", "fr": "Il pleut dehors",
        "de": "Es regnet draussen", "it": "Sta piovendo fuori",
        "pt": "Esta chovendo la fora", "ja": "soto wa ame desu",
        "zh": "waimian xiayu le", "ko": "bakke biga wayo",
        "ar": "innaha tumtir fi alkharij", "vi": "Ben ngoai troi dang mua"}),
    ("I am hungry", {
        "es": "Tengo hambre", "fr": "J'ai faim", "de": "Ich habe Hunger",
        "it": "Ho fame", "pt": "Estou com fome", "ja": "onaka ga suita",
        "zh": "wo e le", "ko": "baegopayo", "ar": "ana jaie",
        "vi": "Toi doi bung"}),
    ("The food is delicious", {
        "es": "La comida esta deliciosa", "fr": "La nourriture est delicieuse",
        "de": "Das Essen ist lecker", "it": "Il cibo e delizioso",
        "pt": "A comida esta deliciosa", "ja": "tabemono ga oishii desu",
        "zh": "fan hen haochi", "ko": "eumsigi masisseoyo",
        "ar": "altaeam ladhidh", "vi": "Do an rat ngon"}),
    ("I would like a coffee", {
        "es": "Me gustaria un cafe", "fr": "Je voudrais un cafe",
        "de": "Ich moechte einen Kaffee", "it": "Vorrei un caffe",
        "pt": "Eu gostaria de um cafe", "ja": "koohii wo kudasai",
        "zh": "wo yao yi bei kafei", "ko": "keopi juseyo",
        "ar": "urid qahwa", "vi": "Toi muon mot ly ca phe"}),
    ("The check please", {
        "es": "La cuenta por favor", "fr": "L'addition s'il vous plait",
        "de": "Die Rechnung bitte", "it": "Il conto per favore",
        "pt": "A conta por favor", "ja": "okaikei onegaishimasu",
        "zh": "maidan", "ko": "gyesanseo juseyo",
        "ar": "alhisab min fadlik", "vi": "Cho toi xin hoa don"}),
    ("Where is the bathroom?", {
        "es": "Donde esta el bano?", "fr": "Ou sont les toilettes?",
        "de": "Wo ist die Toilette?", "it": "Dove e il bagno?",
        "pt": "Onde fica o banheiro?", "ja": "toire wa doko desu ka?",
        "zh": "xishoujian zai nali?", "ko": "hwajangsil eodi issoyo?",
        "ar": "ayna alhammam?", "vi": "Nha ve sinh o dau?"}),
    ("I am lost", {
        "es": "Estoy perdido", "fr": "Je suis perdu", "de": "Ich habe mich verlaufen",
        "it": "Mi sono perso", "pt": "Estou perdido", "ja": "michi ni mayoimashita",
        "zh": "wo milu le", "ko": "gireul ireosseoyo", "ar": "ana dael",
        "vi": "Toi bi lac duong"}),
    ("Call a doctor please", {
        "es": "Llame a un medico por favor", "fr": "Appelez un medecin s'il vous plait",
        "de": "Rufen Sie bitte einen Arzt", "it": "Chiami un medico per favore",
        "pt": "Chame um medico por favor", "ja": "isha wo yonde kudasai",
        "zh": "qing jiao yisheng", "ko": "uisareul bulleo juseyo",
        "ar": "istadei tabiban min fadlik", "vi": "Xin goi bac si"}),
    ("I have a reservation", {
        "es": "Tengo una reserva", "fr": "J'ai une reservation",
        "de": "Ich habe eine Reservierung", "it": "Ho una prenotazione",
        "pt": "Tenho uma reserva", "ja": "yoyaku ga arimasu",
        "zh": "wo you yuding", "ko": "yeyakhaesseoyo",
        "ar": "ladayya hajz", "vi": "Toi co dat cho truoc"}),
    ("The meeting starts at nine", {
        "es": "La reunion empieza a las nueve", "fr": "La reunion commence a neuf heures",
        "de": "Die Besprechung beginnt um neun", "it": "La riunione inizia alle nove",
        "pt": "A reuniao comeca as nove", "ja": "kaigi wa kuji ni hajimarimasu",
        "zh": "huiyi jiu dian kaishi", "ko": "hoeuineun ahop sie sijakhaeyo",
        "ar": "yabda alijtimae fi altasiea", "vi": "Cuoc hop bat dau luc chin gio"}),
    ("Please send me the report", {
        "es": "Por favor envieme el informe", "fr": "Veuillez m'envoyer le rapport",
        "de": "Bitte senden Sie mir den Bericht", "it": "Per favore inviami il rapporto",
        "pt": "Por favor me envie o relatorio", "ja": "repooto wo okutte kudasai",
        "zh": "qing ba baogao fa gei wo", "ko": "bogoseoreul bonae juseyo",
        "ar": "arsil li altaqrir min fadlik", "vi": "Vui long gui cho toi bao cao"}),
    ("The invoice is attached", {
        "es": "La factura esta adjunta", "fr": "La facture est jointe",
        "de": "Die Rechnung ist beigefuegt", "it": "La fattura e allegata",
        "pt": "A fatura esta anexada", "ja": "seikyuusho wo tenpu shimashita",
        "zh": "fapiao yi fujia", "ko": "cheongguseoga cheombudoeeo isseoyo",
        "ar": "alfatura murfaqa", "vi": "Hoa don duoc dinh kem"}),
    ("Happy birthday", {
        "es": "Feliz cumpleanos", "fr": "Joyeux anniversaire",
        "de": "Alles Gute zum Geburtstag", "it": "Buon compleanno",
        "pt": "Feliz aniversario", "ja": "otanjoubi omedetou",
        "zh": "shengri kuaile", "ko": "saengil chukhahaeyo",
        "ar": "eid milad saeid", "vi": "Chuc mung sinh nhat"}),
    ("Congratulations on your new job", {
        "es": "Felicidades por tu nuevo trabajo", "fr": "Felicitations pour ton nouveau travail",
        "de": "Glueckwunsch zum neuen Job", "it": "Congratulazioni per il nuovo lavoro",
        "pt": "Parabens pelo novo emprego", "ja": "atarashii shigoto omedetou",
        "zh": "gongxi ni de xin gongzuo", "ko": "sae jikjang chukhahaeyo",
        "ar": "mabruk ala alamal aljadid", "vi": "Chuc mung cong viec moi"}),
    ("I love this book", {
        "es": "Me encanta este libro", "fr": "J'adore ce livre",
        "de": "Ich liebe dieses Buch", "it": "Io amo questo libro",
        "pt": "Eu amo este livro", "ja": "kono hon ga daisuki desu",
        "zh": "wo ai zhe ben shu", "ko": "i chaegeul saranghaeyo",
        "ar": "uhibb hadha alkitab", "vi": "Toi thich cuon sach nay"}),
    ("The movie was very interesting", {
        "es": "La pelicula fue muy interesante", "fr": "Le film etait tres interessant",
        "de": "Der Film war sehr interessant", "it": "Il film era molto interessante",
        "pt": "O filme foi muito interessante", "ja": "eiga wa totemo omoshirokatta",
        "zh": "dianying hen youqu", "ko": "yeonghwaga jeongmal jaemiisseosseoyo",
        "ar": "kan alfilm mumtiean jiddan", "vi": "Bo phim rat thu vi"}),
    ("I am learning a new language", {
        "es": "Estoy aprendiendo un nuevo idioma", "fr": "J'apprends une nouvelle langue",
        "de": "Ich lerne eine neue Sprache", "it": "Sto imparando una nuova lingua",
        "pt": "Estou aprendendo um novo idioma", "ja": "atarashii gengo wo benkyou shiteimasu",
        "zh": "wo zai xue xin yuyan", "ko": "sae eoneoreul baeugo isseoyo",
        "ar": "ataeallam lugha jadida", "vi": "Toi dang hoc mot ngon ngu moi"}),
    ("Practice makes perfect", {
        "es": "La practica hace al maestro", "fr": "C'est en forgeant qu'on devient forgeron",
        "de": "Uebung macht den Meister", "it": "La pratica rende perfetti",
        "pt": "A pratica leva a perfeicao", "ja": "renshuu wa kanpeki wo tsukuru",
        "zh": "shulian sheng qiao", "ko": "yeonseubi wanbyeogeul mandeureoyo",
        "ar": "almumarasa tasnae alitqan", "vi": "Co cong mai sat co ngay nen kim"}),
    ("The cat is sleeping on the sofa", {
        "es": "El gato esta durmiendo en el sofa", "fr": "Le chat dort sur le canape",
        "de": "Die Katze schlaeft auf dem Sofa", "it": "Il gatto dorme sul divano",
        "pt": "O gato esta dormindo no sofa", "ja": "neko ga sofa de nete imasu",
        "zh": "mao zai shafa shang shuijiao", "ko": "goyangiga sopaeseo jago isseoyo",
        "ar": "alqitt yanam ala alarika", "vi": "Con meo dang ngu tren ghe sofa"}),
    ("My flight leaves at noon", {
        "es": "Mi vuelo sale al mediodia", "fr": "Mon vol part a midi",
        "de": "Mein Flug geht um zwoelf", "it": "Il mio volo parte a mezzogiorno",
        "pt": "Meu voo sai ao meio-dia", "ja": "watashi no hikouki wa shougo ni demasu",
        "zh": "wo de hangban zhongwu qifei", "ko": "je bihaenggineun jeongoe tteonayo",
        "ar": "tughadir rihlati zuhran", "vi": "Chuyen bay cua toi cat canh luc trua"}),
    ("Can you repeat that slowly?", {
        "es": "Puedes repetir eso despacio?", "fr": "Pouvez-vous repeter lentement?",
        "de": "Koennen Sie das langsam wiederholen?", "it": "Puoi ripeterlo lentamente?",
        "pt": "Pode repetir devagar?", "ja": "yukkuri kurikaeshite kuremasu ka?",
        "zh": "ni neng man man chongfu ma?", "ko": "cheoncheonhi dasi malhae jusillaeyo?",
        "ar": "hal yumkinuk tikrar dhalik bibut?", "vi": "Ban co the lap lai cham hon khong?"}),
    ("I will call you later", {
        "es": "Te llamare mas tarde", "fr": "Je t'appellerai plus tard",
        "de": "Ich rufe dich spaeter an", "it": "Ti chiamero piu tardi",
        "pt": "Vou te ligar mais tarde", "ja": "ato de denwa shimasu",
        "zh": "wo dengyixia da gei ni", "ko": "najunge jeonhwa halgeyo",
        "ar": "saattasil bik lahiqan", "vi": "Toi se goi cho ban sau"}),
    ("Turn left at the corner", {
        "es": "Gira a la izquierda en la esquina", "fr": "Tournez a gauche au coin",
        "de": "Biegen Sie an der Ecke links ab", "it": "Gira a sinistra all'angolo",
        "pt": "Vire a esquerda na esquina", "ja": "kado wo hidari ni magatte kudasai",
        "zh": "zai zhuanjiao zuo zhuan", "ko": "motungieseo oenjjogeuro doseyo",
        "ar": "inataf yasaran eind alzawiya", "vi": "Re trai o goc duong"}),
    ("The library opens at eight", {
        "es": "La biblioteca abre a las ocho", "fr": "La bibliotheque ouvre a huit heures",
        "de": "Die Bibliothek oeffnet um acht", "it": "La biblioteca apre alle otto",
        "pt": "A biblioteca abre as oito", "ja": "toshokan wa hachiji ni akimasu",
        "zh": "tushuguan ba dian kaimen", "ko": "doseogwaneun yeodeol sie yeoreoyo",
        "ar": "taftah almaktaba fi althamina", "vi": "Thu vien mo cua luc tam gio"}),
    ("I bought a new phone", {
        "es": "Compre un telefono nuevo", "fr": "J'ai achete un nouveau telephone",
        "de": "Ich habe ein neues Handy gekauft", "it": "Ho comprato un telefono nuovo",
        "pt": "Comprei um telefone novo", "ja": "atarashii denwa wo kaimashita",
        "zh": "wo maile xin shouji", "ko": "sae hyudaeponeul sasseoyo",
        "ar": "ishtarayt hatifan jadidan", "vi": "Toi da mua dien thoai moi"}),
    ("The train is delayed", {
        "es": "El tren esta retrasado", "fr": "Le train est en retard",
        "de": "Der Zug hat Verspaetung", "it": "Il treno e in ritardo",
        "pt": "O trem esta atrasado", "ja": "densha ga okurete imasu",
        "zh": "huoche wandian le", "ko": "gichaga yeonchakdoeeoyo",
        "ar": "taakhkhar alqitar", "vi": "Tau bi tre"}),
]

TARGET_LANGS = ["es", "fr", "de", "it", "pt", "ja", "zh", "ko", "ar", "vi"]
LANG_WEIGHTS = [22, 18, 16, 10, 10, 7, 7, 4, 3, 3]

SAVED_LABELS = ["Greetings", "Polite phrases", "Travel", "Emergency", "Food",
                "Practice", "Hobbies", "Work", "Shopping", "Directions",
                "Weather", "Family", "Health", "Small talk"]

# label -> phrase indexes that fit it (loose thematic grouping)
LABEL_PHRASES = {
    "Greetings": [0, 1, 2, 11, 12],
    "Polite phrases": [3, 4, 8, 34],
    "Travel": [5, 6, 19, 20, 22, 33, 39],
    "Emergency": [8, 20, 21],
    "Food": [15, 16, 17, 18],
    "Practice": [9, 10, 30, 31, 34],
    "Hobbies": [28, 29, 37],
    "Work": [23, 24, 25, 27, 35],
    "Shopping": [7, 38],
    "Directions": [5, 6, 19, 36],
    "Weather": [13, 14],
    "Family": [26, 27, 35],
    "Health": [8, 21],
    "Small talk": [0, 12, 13, 29, 35],
}

# ---------------------------------------------------------------------------
# Glossary vocab: domain -> list of (en, {es, fr, de, it, pt}) — matching the
# existing glossaries, which only use Romance/Germanic target languages.
# ---------------------------------------------------------------------------
GLOSSARY_VOCAB = {
    "Tech": [
        ("computer", {"es": "computadora", "fr": "ordinateur", "de": "Computer", "it": "computer", "pt": "computador"}),
        ("keyboard", {"es": "teclado", "fr": "clavier", "de": "Tastatur", "it": "tastiera", "pt": "teclado"}),
        ("screen", {"es": "pantalla", "fr": "ecran", "de": "Bildschirm", "it": "schermo", "pt": "tela"}),
        ("software", {"es": "programa", "fr": "logiciel", "de": "Software", "it": "software", "pt": "programa"}),
        ("network", {"es": "red", "fr": "reseau", "de": "Netzwerk", "it": "rete", "pt": "rede"}),
        ("printer", {"es": "impresora", "fr": "imprimante", "de": "Drucker", "it": "stampante", "pt": "impressora"}),
        ("password", {"es": "contrasena", "fr": "mot de passe", "de": "Passwort", "it": "password", "pt": "senha"}),
        ("file", {"es": "archivo", "fr": "fichier", "de": "Datei", "it": "file", "pt": "arquivo"}),
        ("mouse", {"es": "raton", "fr": "souris", "de": "Maus", "it": "mouse", "pt": "mouse"}),
        ("server", {"es": "servidor", "fr": "serveur", "de": "Server", "it": "server", "pt": "servidor"}),
    ],
    "Food": [
        ("bread", {"es": "pan", "fr": "pain", "de": "Brot", "it": "pane", "pt": "pao"}),
        ("cheese", {"es": "queso", "fr": "fromage", "de": "Kaese", "it": "formaggio", "pt": "queijo"}),
        ("wine", {"es": "vino", "fr": "vin", "de": "Wein", "it": "vino", "pt": "vinho"}),
        ("meat", {"es": "carne", "fr": "viande", "de": "Fleisch", "it": "carne", "pt": "carne"}),
        ("fish", {"es": "pescado", "fr": "poisson", "de": "Fisch", "it": "pesce", "pt": "peixe"}),
        ("apple", {"es": "manzana", "fr": "pomme", "de": "Apfel", "it": "mela", "pt": "maca"}),
        ("milk", {"es": "leche", "fr": "lait", "de": "Milch", "it": "latte", "pt": "leite"}),
        ("egg", {"es": "huevo", "fr": "oeuf", "de": "Ei", "it": "uovo", "pt": "ovo"}),
        ("rice", {"es": "arroz", "fr": "riz", "de": "Reis", "it": "riso", "pt": "arroz"}),
        ("soup", {"es": "sopa", "fr": "soupe", "de": "Suppe", "it": "zuppa", "pt": "sopa"}),
    ],
    "Business": [
        ("meeting", {"es": "reunion", "fr": "reunion", "de": "Besprechung", "it": "riunione", "pt": "reuniao"}),
        ("contract", {"es": "contrato", "fr": "contrat", "de": "Vertrag", "it": "contratto", "pt": "contrato"}),
        ("invoice", {"es": "factura", "fr": "facture", "de": "Rechnung", "it": "fattura", "pt": "fatura"}),
        ("company", {"es": "empresa", "fr": "entreprise", "de": "Unternehmen", "it": "azienda", "pt": "empresa"}),
        ("budget", {"es": "presupuesto", "fr": "budget", "de": "Budget", "it": "bilancio", "pt": "orcamento"}),
        ("customer", {"es": "cliente", "fr": "client", "de": "Kunde", "it": "cliente", "pt": "cliente"}),
        ("report", {"es": "informe", "fr": "rapport", "de": "Bericht", "it": "rapporto", "pt": "relatorio"}),
        ("deadline", {"es": "fecha limite", "fr": "date limite", "de": "Frist", "it": "scadenza", "pt": "prazo"}),
        ("salary", {"es": "salario", "fr": "salaire", "de": "Gehalt", "it": "stipendio", "pt": "salario"}),
    ],
    "Travel": [
        ("hotel", {"es": "hotel", "fr": "hotel", "de": "Hotel", "it": "albergo", "pt": "hotel"}),
        ("airport", {"es": "aeropuerto", "fr": "aeroport", "de": "Flughafen", "it": "aeroporto", "pt": "aeroporto"}),
        ("ticket", {"es": "boleto", "fr": "billet", "de": "Fahrkarte", "it": "biglietto", "pt": "bilhete"}),
        ("train", {"es": "tren", "fr": "train", "de": "Zug", "it": "treno", "pt": "trem"}),
        ("bus", {"es": "autobus", "fr": "bus", "de": "Bus", "it": "autobus", "pt": "onibus"}),
        ("passport", {"es": "pasaporte", "fr": "passeport", "de": "Reisepass", "it": "passaporto", "pt": "passaporte"}),
        ("luggage", {"es": "equipaje", "fr": "bagages", "de": "Gepaeck", "it": "bagagli", "pt": "bagagem"}),
        ("map", {"es": "mapa", "fr": "carte", "de": "Karte", "it": "mappa", "pt": "mapa"}),
        ("beach", {"es": "playa", "fr": "plage", "de": "Strand", "it": "spiaggia", "pt": "praia"}),
    ],
    "Medical": [
        ("doctor", {"es": "medico", "fr": "medecin", "de": "Arzt", "it": "medico", "pt": "medico"}),
        ("hospital", {"es": "hospital", "fr": "hopital", "de": "Krankenhaus", "it": "ospedale", "pt": "hospital"}),
        ("medicine", {"es": "medicamento", "fr": "medicament", "de": "Medikament", "it": "medicina", "pt": "medicamento"}),
        ("pain", {"es": "dolor", "fr": "douleur", "de": "Schmerz", "it": "dolore", "pt": "dor"}),
        ("fever", {"es": "fiebre", "fr": "fievre", "de": "Fieber", "it": "febbre", "pt": "febre"}),
        ("pharmacy", {"es": "farmacia", "fr": "pharmacie", "de": "Apotheke", "it": "farmacia", "pt": "farmacia"}),
        ("nurse", {"es": "enfermera", "fr": "infirmiere", "de": "Krankenschwester", "it": "infermiera", "pt": "enfermeira"}),
        ("allergy", {"es": "alergia", "fr": "allergie", "de": "Allergie", "it": "allergia", "pt": "alergia"}),
    ],
    "Legal": [
        ("lawyer", {"es": "abogado", "fr": "avocat", "de": "Anwalt", "it": "avvocato", "pt": "advogado"}),
        ("court", {"es": "tribunal", "fr": "tribunal", "de": "Gericht", "it": "tribunale", "pt": "tribunal"}),
        ("law", {"es": "ley", "fr": "loi", "de": "Gesetz", "it": "legge", "pt": "lei"}),
        ("judge", {"es": "juez", "fr": "juge", "de": "Richter", "it": "giudice", "pt": "juiz"}),
        ("witness", {"es": "testigo", "fr": "temoin", "de": "Zeuge", "it": "testimone", "pt": "testemunha"}),
        ("agreement", {"es": "acuerdo", "fr": "accord", "de": "Vereinbarung", "it": "accordo", "pt": "acordo"}),
        ("fine", {"es": "multa", "fr": "amende", "de": "Geldstrafe", "it": "multa", "pt": "multa"}),
    ],
    "Education": [
        ("school", {"es": "escuela", "fr": "ecole", "de": "Schule", "it": "scuola", "pt": "escola"}),
        ("teacher", {"es": "maestro", "fr": "professeur", "de": "Lehrer", "it": "insegnante", "pt": "professor"}),
        ("student", {"es": "estudiante", "fr": "etudiant", "de": "Student", "it": "studente", "pt": "estudante"}),
        ("book", {"es": "libro", "fr": "livre", "de": "Buch", "it": "libro", "pt": "livro"}),
        ("exam", {"es": "examen", "fr": "examen", "de": "Pruefung", "it": "esame", "pt": "exame"}),
        ("homework", {"es": "tarea", "fr": "devoirs", "de": "Hausaufgaben", "it": "compiti", "pt": "licao de casa"}),
        ("lesson", {"es": "leccion", "fr": "lecon", "de": "Unterricht", "it": "lezione", "pt": "licao"}),
        ("library", {"es": "biblioteca", "fr": "bibliotheque", "de": "Bibliothek", "it": "biblioteca", "pt": "biblioteca"}),
    ],
    "Nature": [
        ("tree", {"es": "arbol", "fr": "arbre", "de": "Baum", "it": "albero", "pt": "arvore"}),
        ("river", {"es": "rio", "fr": "riviere", "de": "Fluss", "it": "fiume", "pt": "rio"}),
        ("mountain", {"es": "montana", "fr": "montagne", "de": "Berg", "it": "montagna", "pt": "montanha"}),
        ("flower", {"es": "flor", "fr": "fleur", "de": "Blume", "it": "fiore", "pt": "flor"}),
        ("forest", {"es": "bosque", "fr": "foret", "de": "Wald", "it": "foresta", "pt": "floresta"}),
        ("bird", {"es": "pajaro", "fr": "oiseau", "de": "Vogel", "it": "uccello", "pt": "passaro"}),
        ("lake", {"es": "lago", "fr": "lac", "de": "See", "it": "lago", "pt": "lago"}),
        ("sky", {"es": "cielo", "fr": "ciel", "de": "Himmel", "it": "cielo", "pt": "ceu"}),
    ],
    "Shopping": [
        ("store", {"es": "tienda", "fr": "magasin", "de": "Geschaeft", "it": "negozio", "pt": "loja"}),
        ("price", {"es": "precio", "fr": "prix", "de": "Preis", "it": "prezzo", "pt": "preco"}),
        ("money", {"es": "dinero", "fr": "argent", "de": "Geld", "it": "denaro", "pt": "dinheiro"}),
        ("discount", {"es": "descuento", "fr": "remise", "de": "Rabatt", "it": "sconto", "pt": "desconto"}),
        ("receipt", {"es": "recibo", "fr": "recu", "de": "Quittung", "it": "ricevuta", "pt": "recibo"}),
        ("cash", {"es": "efectivo", "fr": "especes", "de": "Bargeld", "it": "contanti", "pt": "dinheiro vivo"}),
        ("bag", {"es": "bolsa", "fr": "sac", "de": "Tasche", "it": "borsa", "pt": "sacola"}),
    ],
    "Weather": [
        ("rain", {"es": "lluvia", "fr": "pluie", "de": "Regen", "it": "pioggia", "pt": "chuva"}),
        ("snow", {"es": "nieve", "fr": "neige", "de": "Schnee", "it": "neve", "pt": "neve"}),
        ("wind", {"es": "viento", "fr": "vent", "de": "Wind", "it": "vento", "pt": "vento"}),
        ("sun", {"es": "sol", "fr": "soleil", "de": "Sonne", "it": "sole", "pt": "sol"}),
        ("cloud", {"es": "nube", "fr": "nuage", "de": "Wolke", "it": "nuvola", "pt": "nuvem"}),
        ("storm", {"es": "tormenta", "fr": "tempete", "de": "Sturm", "it": "tempesta", "pt": "tempestade"}),
        ("fog", {"es": "niebla", "fr": "brouillard", "de": "Nebel", "it": "nebbia", "pt": "nevoeiro"}),
    ],
    "Family": [
        ("mother", {"es": "madre", "fr": "mere", "de": "Mutter", "it": "madre", "pt": "mae"}),
        ("father", {"es": "padre", "fr": "pere", "de": "Vater", "it": "padre", "pt": "pai"}),
        ("brother", {"es": "hermano", "fr": "frere", "de": "Bruder", "it": "fratello", "pt": "irmao"}),
        ("sister", {"es": "hermana", "fr": "soeur", "de": "Schwester", "it": "sorella", "pt": "irma"}),
        ("grandmother", {"es": "abuela", "fr": "grand-mere", "de": "Grossmutter", "it": "nonna", "pt": "avo"}),
        ("uncle", {"es": "tio", "fr": "oncle", "de": "Onkel", "it": "zio", "pt": "tio"}),
        ("cousin", {"es": "primo", "fr": "cousin", "de": "Cousin", "it": "cugino", "pt": "primo"}),
    ],
    "Sports": [
        ("soccer", {"es": "futbol", "fr": "football", "de": "Fussball", "it": "calcio", "pt": "futebol"}),
        ("swimming", {"es": "natacion", "fr": "natation", "de": "Schwimmen", "it": "nuoto", "pt": "natacao"}),
        ("team", {"es": "equipo", "fr": "equipe", "de": "Mannschaft", "it": "squadra", "pt": "time"}),
        ("ball", {"es": "pelota", "fr": "ballon", "de": "Ball", "it": "palla", "pt": "bola"}),
        ("race", {"es": "carrera", "fr": "course", "de": "Rennen", "it": "gara", "pt": "corrida"}),
        ("goal", {"es": "gol", "fr": "but", "de": "Tor", "it": "gol", "pt": "gol"}),
        ("coach", {"es": "entrenador", "fr": "entraineur", "de": "Trainer", "it": "allenatore", "pt": "treinador"}),
    ],
}
GLOSSARY_LANGS = ["es", "fr", "de", "it", "pt"]
LANG_NAMES = {"es": "ES", "fr": "FR", "de": "DE", "it": "IT", "pt": "PT"}

FIRST_NAMES = ["Sofia", "Liam", "Maya", "Noah", "Isabella", "Ethan", "Olivia",
               "Lucas", "Amelia", "Mason", "Harper", "Elijah", "Chloe",
               "James", "Grace", "Benjamin", "Zoe", "Henry", "Lily", "Jack",
               "Nora", "Owen", "Ruby", "Leo", "Stella", "Miles", "Hazel",
               "Felix", "Ivy", "Oscar", "Ana", "Diego", "Mei", "Hiro",
               "Fatima", "Omar", "Linh", "Minh", "Priya", "Raj", "Elena",
               "Marco", "Camille", "Pierre", "Ingrid"]
LAST_NAMES = ["Nguyen", "Garcia", "Kim", "Patel", "Silva", "Mueller", "Rossi",
              "Dubois", "Tanaka", "Ali", "Johnson", "Brown", "Davis", "Miller",
              "Wilson", "Moore", "Anderson", "Thomas", "Jackson", "White",
              "Harris", "Clark", "Lewis", "Walker", "Hall", "Young", "King",
              "Wright", "Lopez", "Hill", "Scott", "Green", "Adams", "Baker",
              "Nelson", "Carter", "Mitchell", "Perez", "Roberts", "Turner",
              "Phillips", "Campbell", "Parker", "Evans", "Edwards"]

N_NEW_USERS = 45


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def rand_ts():
    span = int((HIST_END - HIST_START).total_seconds() // 60)
    return iso(HIST_START + datetime.timedelta(minutes=rng.randint(0, span)))


def make_pair():
    """Return (source_lang, target_lang, source_text, translated_text)."""
    idx = rng.randrange(len(PHRASES))
    en, trans = PHRASES[idx]
    lang = rng.choices(TARGET_LANGS, weights=LANG_WEIGHTS)[0]
    if rng.random() < 0.75:
        return "en", lang, en, trans[lang]
    return lang, "en", trans[lang], en


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    next_user = db.execute("SELECT MAX(id)+1 FROM translation_users").fetchone()[0]
    next_hist = db.execute("SELECT MAX(id)+1 FROM translation_history").fetchone()[0]
    next_saved = db.execute("SELECT MAX(id)+1 FROM translation_saved").fetchone()[0]
    next_gloss = db.execute("SELECT MAX(id)+1 FROM translation_glossaries").fetchone()[0]
    existing_gloss_names = {r["name"] for r in
                            db.execute("SELECT name FROM translation_glossaries")}
    existing_usernames = {r["username"] for r in
                          db.execute("SELECT username FROM translation_users")}

    # ------------------------------------------------------------------ users
    users_new = []
    used = set(existing_usernames)
    combos = [(f, l) for f in FIRST_NAMES for l in LAST_NAMES]
    rng.shuffle(combos)
    for first, last in combos:
        if len(users_new) >= N_NEW_USERS:
            break
        uname = f"{first.lower()}_{last.lower()}"
        if uname in used:
            continue
        used.add(uname)
        uid = next_user
        next_user += 1
        users_new.append({
            "id": uid, "username": uname,
            "password": "pass" + str(uid) * 3 if uid < 10 else f"pass{uid}{uid}",
            "name": f"{first} {last}",
            "email": f"{first.lower()}.{last.lower()}@email.com"})

    all_user_ids = ([1, 2, 3, 4, 5] + [u["id"] for u in users_new])

    # ---------------------------------------------------------------- history
    # Per-user volume kept far below the ~500-row unbounded page render cap.
    hist_counts = {1: 120, 2: 90, 3: 90, 4: 90, 5: 90}
    for u in users_new:
        hist_counts[u["id"]] = rng.randint(60, 90)

    history_new = []
    for uid, n in hist_counts.items():
        for _ in range(n):
            sl, tl, st, tt = make_pair()
            history_new.append({
                "id": next_hist, "user_id": uid, "source_lang": sl,
                "target_lang": tl, "source_text": st, "translated_text": tt,
                "timestamp": rand_ts()})
            next_hist += 1

    # ------------------------------------------------------------------ saved
    saved_counts = {1: 20, 2: 18, 3: 18, 4: 18, 5: 18}
    for u in users_new:
        saved_counts[u["id"]] = rng.randint(15, 28)

    saved_new = []
    for uid, n in saved_counts.items():
        labels = rng.sample(SAVED_LABELS, min(len(SAVED_LABELS), rng.randint(3, 6)))
        seen = set()
        made = 0
        attempts = 0
        while made < n and attempts < n * 20:
            attempts += 1
            label = rng.choice(labels)
            idx = rng.choice(LABEL_PHRASES[label])
            en, trans = PHRASES[idx]
            lang = rng.choices(TARGET_LANGS, weights=LANG_WEIGHTS)[0]
            if rng.random() < 0.85:
                sl, tl, st, tt = "en", lang, en, trans[lang]
            else:
                sl, tl, st, tt = lang, "en", trans[lang], en
            key = (sl, tl, st, label)
            if key in seen:
                continue
            seen.add(key)
            saved_new.append({
                "id": next_saved, "user_id": uid, "source_lang": sl,
                "target_lang": tl, "source_text": st, "translated_text": tt,
                "label": label})
            next_saved += 1
            made += 1

    # ------------------------------------------------------------- glossaries
    gloss_counts = {1: 2, 2: 2, 3: 2, 4: 2, 5: 2}
    for u in users_new:
        gloss_counts[u["id"]] = rng.randint(1, 3)

    domains = list(GLOSSARY_VOCAB)
    used_names = set(existing_gloss_names)
    glossaries_new = []
    for uid, n in gloss_counts.items():
        for _ in range(n):
            name = None
            for _try in range(40):
                domain = rng.choice(domains)
                tgt = rng.choice(GLOSSARY_LANGS)
                suffix = rng.choice([" Terms", ""])
                cand = f"{domain}{suffix} EN-{LANG_NAMES[tgt]}"
                if cand not in used_names:
                    name = cand
                    break
            if name is None:
                continue  # user keeps fewer glossaries; names exhausted
            used_names.add(name)
            vocab = GLOSSARY_VOCAB[domain]
            k = rng.randint(max(4, len(vocab) - 3), len(vocab))
            entries = [{"source": en, "target": tr[tgt]}
                       for en, tr in rng.sample(vocab, k)]
            glossaries_new.append({
                "id": next_gloss, "user_id": uid, "name": name,
                "source_lang": "en", "target_lang": tgt,
                "entries": json.dumps(entries)})
            next_gloss += 1

    print(f"users: +{len(users_new)}, history: +{len(history_new)}, "
          f"saved: +{len(saved_new)}, glossaries: +{len(glossaries_new)}")
    per_user_hist = max(hist_counts.values())
    print(f"max history rows for any single user (page render check): "
          f"{per_user_hist} + existing")
    if dry:
        for h in history_new[:5]:
            print(" H", h["user_id"], h["source_lang"], "->", h["target_lang"],
                  "|", h["source_text"][:40], "=>", h["translated_text"][:40])
        for s in saved_new[:3]:
            print(" S", s["user_id"], s["label"], "|", s["source_text"][:40])
        for g in glossaries_new[:5]:
            print(" G", g["user_id"], g["name"],
                  f"({len(json.loads(g['entries']))} entries)")
        return

    bdir = ROOT / "data" / "backups" / "translation-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "users": [u["id"] for u in users_new],
        "history": [h["id"] for h in history_new],
        "saved": [s["id"] for s in saved_new],
        "glossaries": [g["id"] for g in glossaries_new]}, indent=1))

    for table, rows in (("users", users_new), ("history", history_new),
                        ("saved", saved_new), ("glossaries", glossaries_new)):
        if not rows:
            continue
        cols = list(rows[0].keys())
        db.executemany(
            f"INSERT INTO translation_{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [[r[c] for c in cols] for r in rows])

    # Sync content-linked FTS indexes for the tables we touched.
    for fts in ("fts_translation_history", "fts_translation_saved"):
        db.execute(f"INSERT INTO {fts}({fts}) VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
