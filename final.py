from flask import Flask, render_template_string, request, jsonify
import requests
from bs4 import BeautifulSoup
import os
import json
from datetime import datetime

app = Flask(__name__)
DL_FOLDER = "downloads"
os.makedirs(DL_FOLDER, exist_ok=True)

# Static demo data (replace or expand for all states/districts/courts)
STATES = {"DL": "Delhi"}
DISTRICTS = {"DL": {"ND": "New Delhi"}}
COURT_COMPLEXES = {"ND": {"PHC": "Patiala House Court"}}
COURTS = {"PHC": {"CIVIL": "Civil Court", "CRIMINAL": "Criminal Court"}}
# Mapping for New Delhi documents; you may expand for others
DOCUMENT_URLS = {
    "ND": "https://newdelhi.dcourts.gov.in/documents/"
}

@app.route("/")
def index():
    return render_template_string("""
<html><head>
<title>Delhi Court Cause List Downloader</title>
<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<style>
body{font-family:Arial; margin:2rem;}
label{display:block; margin-top:10px;}
select, input[type=date], input[type=text], button { width:300px; margin-top:5px; }
</style>
</head>
<body>
<h2>Delhi Court Cause List Downloader</h2>
<form id="causeForm">
  <label>State:
    <select name="state" id="state" required>
      <option value="">Select State</option>
      {% for k, v in states.items() %}
      <option value="{{k}}">{{v}}</option>
      {% endfor %}
    </select>
  </label>
  <label>District:
    <select name="district" id="district" required>
      <option value="">Select District</option>
    </select>
  </label>
  <label>Court Complex:
    <select name="court_complex" id="court_complex" required>
      <option value="">Select Court Complex</option>
    </select>
  </label>
  <label>Court:
    <select name="court" id="court" required>
      <option value="">Select Court</option>
    </select>
  </label>
  <label>Case Type:
    <select name="case_type" required>
      <option value="CIVIL">Civil</option>
      <option value="CRIMINAL">Criminal</option>
    </select>
  </label>
  <label>Cause List Date:
    <input type="date" name="cause_date" value="{{today}}" required />
  </label>
  <br>
  <button type="submit">Fetch & Download PDFs</button>
</form>
<div id="result"></div>
<script>
$(function(){
  $('#state').change(function(){
    $.getJSON('/districts/'+$(this).val(), function(data){
      let opts='<option value="">Select District</option>';
      $.each(data,function(k,v){opts+='<option value="'+k+'">'+v+'</option>';});
      $('#district').html(opts);
      $('#court_complex').html('<option value="">Select Court Complex</option>'); $('#court').html('<option value="">Select Court</option>');
    });
  });
  $('#district').change(function(){
    $.getJSON('/court_complexes/'+$(this).val(), function(data){
      let opts='<option value="">Select Court Complex</option>';
      $.each(data,function(k,v){opts+='<option value="'+k+'">'+v+'</option>';});
      $('#court_complex').html(opts); $('#court').html('<option value="">Select Court</option>');
    });
  });
  $('#court_complex').change(function(){
    $.getJSON('/courts/'+$(this).val(), function(data){
      let opts='<option value="">Select Court</option>';
      $.each(data,function(k,v){opts+='<option value="'+k+'">'+v+'</option>';});
      $('#court').html(opts);
    });
  });
  $('#causeForm').submit(function(e){
    e.preventDefault(); $('#result').html("Working ...");
    $.ajax({type:'POST',url:'/fetch',data:$(this).serialize(),success:function(data){
        if(data.pdfs.length==0) $('#result').html("No PDFs found.");
        else {
          let html = '<h4>Downloaded PDFs:</h4><ul>';
          data.pdfs.forEach(function(p){html+='<li><a href="'+p.path+'" target="_blank">'+p.title+'</a> <small>'+p.date+'</small></li>';}); html+='</ul>';
          $('#result').html(html+"<p>Also saved metadata to <b>cause_list_output.json</b></p>");
        }
    },error:function(){$('#result').html('Error occurred.');}});
  });
});
</script>
</body>
</html>""", states=STATES, today=datetime.today().strftime('%Y-%m-%d'))

@app.route("/districts/<state>")
def districts(state): return jsonify(DISTRICTS.get(state, {}))
@app.route("/court_complexes/<district>")
def court_complexes(district): return jsonify(COURT_COMPLEXES.get(district, {}))
@app.route("/courts/<court_complex>")
def courts(court_complex): return jsonify(COURTS.get(court_complex, {}))

@app.route("/fetch", methods=["POST"])
def fetch():
    district = request.form["district"]
    date_str = request.form["cause_date"]
    target_url = DOCUMENT_URLS[district]
    r = requests.get(target_url, headers={"User-Agent":"Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")
    date_disp = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d-%m-%Y")
    pdfs = []
    for link in soup.find_all('a',href=True):
        txt, href = link.get_text(strip=True), link['href']
        if href.lower().endswith('.pdf') and date_disp in txt:
            url = href if href.startswith('http') else target_url.rstrip('/')+'/'+href.lstrip('/')
            fname = txt.replace("/","_").replace("\\","_")+".pdf"
            path = os.path.join(DL_FOLDER, fname)
            pdfs.append({"title": txt, "url": url, "date": date_disp, "path": path })
    # Download
    for pdf in pdfs:
        try:
            resp = requests.get(pdf["url"],stream=True)
            with open(pdf["path"],"wb") as f:
                for chunk in resp.iter_content(8192):
                    if chunk: f.write(chunk)
        except Exception as e:
            print("Failed for",pdf["url"],str(e))
    # Save metadata
    with open("cause_list_output.json","w",encoding="utf-8") as f:
        json.dump(pdfs, f, indent=4, ensure_ascii=False)
    return jsonify({"pdfs":[{"title":p["title"],"date":p["date"],"path":p["path"]} for p in pdfs]})

if __name__=="__main__":
    app.run(debug=True)
