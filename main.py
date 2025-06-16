from flask import Flask, request, render_template_string
import os
import requests
from flask_mail import Mail, Message
import openai
import re

# ====== CONFIG ======
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
FACEPP_API_KEY = os.environ.get('FACEPP_API_KEY')
FACEPP_API_SECRET = os.environ.get('FACEPP_API_SECRET')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
# ====================

app = Flask(__name__)

# --- Configurazione Flask-Mail (Gmail) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = MAIL_USERNAME
app.config['MAIL_PASSWORD'] = MAIL_PASSWORD
app.config['MAIL_DEFAULT_SENDER'] = MAIL_USERNAME
mail = Mail(app)

# --- HTML Form ---
HTML_FORM = """
<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Consulenza Estetica Viso</title>
  <link href="https://fonts.googleapis.com/css?family=Montserrat:600,400&display=swap" rel="stylesheet">
  <style>
    body { background: #f9fbfe; font-family: 'Montserrat', Arial, sans-serif; margin:0; }
    .form-container { max-width:430px;margin:46px auto 0 auto;background:#fff;padding:38px 26px 30px 26px;
      border-radius: 20px; box-shadow: 0 8px 32px rgba(60,110,190,0.08); border:1.5px solid #e3eafc;}
    h2 { text-align:center; color:#006ab7; margin-bottom:26px; font-size:1.8rem; font-weight:600;}
    label { display:block; margin-bottom:12px; font-weight:500;}
    input[type="text"], input[type="email"], input[type="number"], select, textarea, input[type="file"] {
      width: 100%; padding: 10px 12px; margin-top: 6px; border: 1px solid #d6e5f5; border-radius: 8px;
      font-size: 1em; background: #f6fbff; transition: border-color 0.2s; box-sizing: border-box; font-family: inherit;}
    input:focus, textarea:focus, select:focus { border-color:#6ec6ff; outline:none; background:#eef6fc;}
    button { width: 100%; margin-top:18px; padding:12px; background:linear-gradient(90deg,#47b5ed,#0085cc); color:#fff;
      border:none; border-radius:10px; font-size:1.1em; font-weight:600; box-shadow:0 4px 20px rgba(0,90,190,0.08);
      cursor:pointer; letter-spacing:0.5px; transition:background 0.2s, box-shadow 0.2s;}
    button:hover { background:linear-gradient(90deg,#0085cc,#47b5ed); box-shadow:0 6px 24px rgba(0,90,190,0.14);}
    .error { color:#c2182b;text-align:center; margin-top:15px;margin-bottom:15px;font-weight:500;}
    .loading { display: none; text-align:center; margin-top:18px;}
    .loading img { width: 38px; vertical-align:middle; margin-right:10px;}
    .loading span { font-size:1.1em; color:#0085cc; font-weight:600;}
    @media (max-width: 500px) {.form-container{margin:20px 4px; padding:18px 5px 12px 5px;} h2{font-size:1.2rem;}}
  </style>
</head>
<body>
  <div class="form-container">
    <h2>Consulenza estetica viso<br>con analisi foto</h2>
    {{ errore|safe }}
    <form method="post" enctype="multipart/form-data" onsubmit="startLoading()">
      <label>Nome: <input name="nome" required></label>
      <label>Cognome: <input name="cognome" required></label>
      <label>Età: <input name="eta" required type="number" min="10" max="120"></label>
      <label>Sesso:
        <select name="sesso" required>
          <option value="Femmina">Femmina</option>
          <option value="Maschio">Maschio</option>
          <option value="Altro">Altro</option>
        </select>
      </label>
      <label>Email: <input name="email" type="email" required></label>
      <label>Carica una foto del viso (ben illuminata): <input type="file" name="foto" accept="image/*" required></label>
      <button id="submit-btn" type="submit">Invia richiesta</button>
      <div class="loading" id="loading-div">
        <img src="https://i.gifer.com/ZZ5H.gif" alt="Caricamento...">
        <span>Analisi in corso...</span>
      </div>
    </form>
  </div>
  <script>
    function startLoading() {
      document.getElementById('submit-btn').style.display = 'none';
      document.getElementById('loading-div').style.display = 'block';
    }
  </script>
</body>
</html>
"""

HTML_THANKS = """
<!doctype html>
<html lang='it'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width,initial-scale=1'>
  <link href="https://fonts.googleapis.com/css?family=Montserrat:600,400&display=swap" rel="stylesheet">
  <style>
    body { background: #f9fbfe; font-family: 'Montserrat', Arial, sans-serif; margin:0;}
    .thanks { max-width:430px;margin:60px auto 0 auto;background:#fff;padding:44px 24px 30px 24px;border-radius:22px;box-shadow:0 6px 32px rgba(60,110,190,0.07);}
    h2 { color:#0085cc;text-align:center; font-size:1.2em;}
    p { text-align:center;font-size:1.06em;margin-bottom:18px;}
    a { display:block; text-align:center; color:#0085cc; text-decoration:underline;}
  </style>
</head>
<body>
  <div class='thanks'>
    <h2>Grazie! La tua richiesta è stata ricevuta.</h2>
    <p>A breve riceverai la tua consulenza estetica via mail.</p>
    <a href="/">Torna al form</a>
  </div>
</body>
</html>
"""

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def email_valida(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

@app.route('/', methods=['GET', 'POST'])
def index():
    errore = ""
    if request.method == 'POST':
        nome = request.form['nome']
        cognome = request.form['cognome']
        eta = request.form['eta']
        sesso = request.form['sesso']
        email = request.form['email']

        # Controllo mail
        if not email_valida(email):
            errore = '<div class="error">Indirizzo email non valido!</div>'
            return render_template_string(HTML_FORM, errore=errore)

        # Controllo e invio file a Face++ senza salvarla
        if 'foto' not in request.files:
            errore = '<div class="error">Carica una foto del viso.</div>'
            return render_template_string(HTML_FORM, errore=errore)
        file = request.files['foto']
        if file.filename == '' or not allowed_file(file.filename):
            errore = '<div class="error">Carica una foto valida (jpg, jpeg, png).</div>'
            return render_template_string(HTML_FORM, errore=errore)

        url = "https://api-us.faceplusplus.com/facepp/v3/detect"
        files = {'image_file': (file.filename, file.stream, file.mimetype)}
        data = {
            'api_key': FACEPP_API_KEY,
            'api_secret': FACEPP_API_SECRET,
            'return_attributes': 'age,gender,skinstatus,blur'
        }
        r = requests.post(url, files=files, data=data)
        result = r.json()
        if 'faces' not in result or not result['faces']:
            errore = '<div class="error">Nessun volto rilevato. Assicurati che la foto sia ben centrata e illuminata.</div>'
            return render_template_string(HTML_FORM, errore=errore)

        face = result['faces'][0]
        blur = face.get('attributes', {}).get('blur', {}).get('blurness', {}).get('value', 100)
        if blur > 0.5:
            errore = '<div class="error">La foto è troppo sfocata. Riprova con una foto più nitida e luminosa.</div>'
            return render_template_string(HTML_FORM, errore=errore)

        age = face.get('attributes', {}).get('age', {}).get('value', 'N/A')
        gender = face.get('attributes', {}).get('gender', {}).get('value', 'N/A')
        skin = face.get('attributes', {}).get('skinstatus', {})

        skin_descr = []
        if skin:
            if skin.get('health') is not None:
                skin_descr.append(f"Salute: {int(skin['health']*100)}%")
            if skin.get('stain') is not None:
                skin_descr.append(f"Macchie: {int(skin['stain']*100)}%")
            if skin.get('acne') is not None:
                skin_descr.append(f"Acne: {int(skin['acne']*100)}%")
            if skin.get('dark_circle') is not None:
                skin_descr.append(f"Occhiaie: {int(skin['dark_circle']*100)}%")
        skin_descr = ", ".join(skin_descr) if skin_descr else "N/A"

        # Prompt per ChatGPT personalizzato
        PROMPT = f"""
Ricevi i seguenti dati da una persona che vuole un consiglio estetico personalizzato:
Nome: {nome}
Cognome: {cognome}
Età dichiarata: {eta}
Sesso dichiarato: {sesso}
Età stimata Face++: {age}
Genere stimato Face++: {gender}
Analisi della pelle Face++: {skin_descr}

Fornisci una descrizione estetica dettagliata del suo viso e della pelle. Consiglia come può migliorare la sua skincare quotidiana, usando suggerimenti motivanti. Dì alla persona che è importante prendersi cura della propria pelle ogni giorno e spiega quali sono le problematiche a cui può andare incontro (es. invecchiamento precoce, perdita di luminosità, imperfezioni, ecc) se non si cura la pelle. Dai consigli chiari e gentili. Concludi con una frase motivazionale personalizzata.

Rispondi in italiano, con tono positivo, affettuoso e professionale.
"""

        # Richiesta a OpenAI
        try:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Sei una consulente di bellezza professionale e gentile."},
                    {"role": "user", "content": PROMPT}
                ],
                max_tokens=800
            )
            risposta = response.choices[0].message.content
        except Exception as e:
            return f"Errore OpenAI: {e}"

        risposta_html = risposta.replace('\n','<br>')

        mail_html = f"""
        <div style="background:#fff; border-radius:18px; font-family:Montserrat,Arial,sans-serif; color:#222;
        max-width:500px; margin:auto; border:1.5px solid #e3eafc; box-shadow:0 8px 32px rgba(60,110,190,0.08); padding:28px;">
            <h2 style="text-align:center; color:#0085cc; font-size:1.15em; margin-bottom:26px; margin-top:0; font-weight:600;">
                Consulenza estetica viso</h2>
            <hr style="margin:18px 0 18px 0;border:none;border-top:1.2px solid #e3eafc;">
            <div style="font-size:1.06em;line-height:1.65; color:#222;">
                {risposta_html}
            </div>
            <br>
            <p style="text-align:center; color:#aaa; font-size:.97em;">
                Questa consulenza è fornita a scopo informativo e non sostituisce il parere di un professionista qualificato.<br>
                <br>
                <i>Powered by Face++ e ChatGPT</i>
            </p>
        </div>
        """

        try:
            msg = Message(
                subject="La tua consulenza estetica personalizzata",
                sender=MAIL_USERNAME,
                recipients=[email]
            )
            msg.html = mail_html
            msg.body = risposta
            mail.send(msg)
        except Exception as e:
            return f"Risposta generata ma errore invio mail: {e}<br><br><b>Risposta:</b><br><pre>{risposta}</pre>"

        return HTML_THANKS

    # GET
    return render_template_string(HTML_FORM, errore=errore)

if __name__ == '__main__':
    app.run(debug=True)