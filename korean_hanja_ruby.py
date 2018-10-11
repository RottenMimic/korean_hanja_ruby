# -*- coding: utf-8 -*-

import Tkinter as tk, ScrolledText
import urllib2, re
import sqlite3
import os, time, codecs, sys, commands

def format_path(path):
   return os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), path)

db_path=format_path('hanja.db')
template_path=format_path('template.html')
test_flag=False
word_count=0

#logging window
class logging():
   def __init__(self):
      self.root=tk.Tk()
      self.root.title('log window')
      self.scrltx=ScrolledText.ScrolledText(self.root)
      self.scrltx.pack(fill='both', expand=True)
      self.scrltx.config(state=tk.DISABLED)
      
   def log(self, tx):
      self.scrltx.insert(tk.END, tx+'\r\n')

def forcheck_db():
   def create_db():
      conn=sqlite3.connect(db_path)
      c=conn.cursor()
      c.execute('CREATE TABLE hanja (korean text, hanja text)')
      c.execute('CREATE TABLE fuzzy (korean text, refer text)')
      c.execute('CREATE TABLE no_data (korean text)')
      conn.commit()
      conn.close()
      
   #file exist
   if os.path.isfile(db_path):
      #check format
      conn=sqlite3.connect(db_path)
      c=conn.cursor()
      c.execute('SELECT * FROM fuzzy WHERE korean=?', u'대')
      c.execute('SELECT * FROM hanja WHERE korean=?', u'대')
      c.execute('SELECT * FROM no_data WHERE korean=?', u'대')
      conn.close()

   else:
      create_db()

class control_db():
   def __init__(self):
      self.conn=sqlite3.connect(db_path)
      self.c=self.conn.cursor()
   
   def __del__(self):
      self.conn.close()
      
   def search_one(self, tx, item=None):
      if item: 
         if not(type(item)==type(())):
            item=(item,)
         self.c.execute(tx, item)
      else:
         self.c.execute(tx)
      k=self.c.fetchone()
      return k
      
   def insert(self, tx, item=None):
      if item:
         if not(type(item)==type(())):
            item=(item,)
         self.c.execute(tx, item)
      else:
         self.c.execute(tx)
      self.conn.commit()

def check_db(tx):
   log(tx)
   db=control_db()
   #hanja
   result=db.search_one('SELECT * FROM hanja WHERE korean=?', tx) #(korean, hanja)
   if result: 
      log('hanja found')
      return result
   #fuzzy
   result=db.search_one('SELECT * FROM fuzzy WHERE korean=?', tx) #(korean, fuzzy)
   if result: 
      log('fuzzy found')
      result=db.search_one('SELECT * FROM hanja WHERE korean=?', result[1]) #(korean, hanja)
      if result:
         return result
   #no data      
   result=db.search_one('SELECT * FROM no_data WHERE korean=?', tx) #korean
   if result: 
      log('no_data found')
      return tx
      
   #naver
   return connect_naver(tx)
   
def connect_naver(tx):
   #must be clean word, no punction
   log('search word:\t'+ tx)
   
   def no_data():
      db=control_db()
      db.insert('INSERT INTO no_data VALUES (?)', (tx))
   
   #check url
   url='https://hanja.dict.naver.com/search?query='+urllib2.quote(tx.encode('utf-8'))
   
   #get naver data
   html=urllib2.urlopen(url).read()
   
   #if not find
   if '</span></strong>' in html:
      log('naver not found word')
      no_data()
      return tx
   
   #parse html: get hanja & korean
   hanja_arr=re.findall('"\/word\?id=(.*?)">(.*?)</a>', html)
   korean_arr=re.findall('"\/word\?id=(.*?)"><span><b>(.*?)</b>', html)
      
   #check parsed data
   if len(hanja_arr)==0 or len(korean_arr)==0:
      log('naver not found word 2')
      no_data()
      return tx
   
   korean=unicode(korean_arr[0][1], 'utf_8')
   hanja=unicode(hanja_arr[0][1], 'utf_8')
   
   #save to db
   db=control_db()
   db.insert('INSERT INTO hanja VALUES(?,?)', (korean, hanja))
   db.insert('INSERT INTO fuzzy VALUES(?,?)', (tx, korean))
   
   return (korean, hanja)

def export_html(total_tx, word_tx):
   log('export html')
   #load template
   try:
      with open(template_path, 'rb') as f:
         html=f.read()
   except:
      log('template not found')
      html=u'<html><head>korean hanja</head><body>{1}<hr />{2}</body></html>'
   
   try:
      html=unicode(html, 'utf_8')
   except:
      pass
   #create html
   html=html.replace('{1}', total_tx).replace('{2}', word_tx)
   #save html
   path=str(int(time.time())) +'.html'
   path=format_path(path)
   try:
      print path
   except:
      pass
   log(path)
   with codecs.open(path, 'wb', encoding='utf-8') as f:
      f.write(html)
   log('save html done')
   print ('html saved')
   
def process_raw_text(tx):
   log('raw_text')
   #to utf8
   try:
      tx=unicode(tx, 'utf_8')
   except:
      pass
   #check by word
   total_tx=''
   tmp_tx=''
   words={}
   not_found_word=[]
   
   def format_word(korean,hanja):
      return u'<ruby>%1<rt>%2</rt></ruby>'.replace('%1', korean).replace('%2', hanja)
   
   for char in tx:
      if ord(char)<256:
         #punction or english
         if tmp_tx:
            #something in tmp_tx
            if tmp_tx in words:
               #hanja
               total_tx+=format_word(tmp_tx, words[tmp_tx])
            elif tmp_tx in not_found_word:
               total_tx+=tmp_tx
            else:
               result=check_db(tmp_tx)
               
               if type(result)==type(u''):
                  #no searched data
                  not_found_word+=[tmp_tx]
                  total_tx+=tmp_tx
               elif type(result)==type(()):
                  #data searched
                  if len(result)<2:
                     log('len < 2')
                     not_found_word+=[tmp_tx]
                     total_tx+=tmp_tx
                  else:
                     #(korean, hanja)
                     total_tx+=format_word(tmp_tx, result[1])
                     if not(result in words):
                        words[result[0]]=result[1]
               else:
                  #unknown type
                  log('unknown type:\t' + str(type(result)))
                  total_tx+=tmp_tx
         #reset
         tmp_tx=''
         total_tx+=char
      else:
         #2 byte char
         tmp_tx+=char
      
   total_tx=total_tx.replace(u'\r', u'').replace(u'\n', u'<br />')
   word_tx=''
   for w in words:
      word_tx+='%1 %2<br />'.replace('%1', w).replace('%2', words[w])
   
   export_html(total_tx, word_tx)

def main_gui():
   root=tk.Tk()
   root.title('Korean Hanja Ruby')
   #label
   label=tk.Label(root, text='Paste: Ctrl+V').pack(fill='x')
   #scrolledtext
   p=ScrolledText.ScrolledText(root)
   p.pack(fill='both', expand=True)
   #button
   def button_call_back():
       tx=p.get(1.0, tk.END)
       print('executing...')
       process_raw_text(tx)
   tk.Button(root, text="SEND", command=button_call_back).pack(fill='x')
   
   print('ready')
   tk.mainloop()
   
def log(tx):
   if test_flag:
      obj_log.log(tx)

if __name__ == "__main__":
   forcheck_db()
   main_gui()
else:
   test_flag=True
   
if test_flag:
   obj_log=logging()
   
