#! /usr/bin/env python
#
# This library is free software, distributed under the terms of
# the GNU Lesser General Public License Version 3, or any later version.
# See the COPYING file included in this archive
#

import pygtk
pygtk.require('2.0')
import sys, gtk, gobject, cairo
import math
from math import ceil

from twisted.internet import gtk2reactor
gtk2reactor.install()
import twisted.internet.reactor
import entangled.dtuple

import entangled.kademlia.contact
import entangled.kademlia.msgtypes

import hashlib

from os.path import getsize

class SplitFile(object):
  # Quebra o arquivo em pedacos do tamanho de slice_size e retorna um par de chave-valor, onde a chave e SHA-1 do valor
  def __init__(self):
    self.slice_size = 6*1024 #6 kb
    # self.slice_size = 256*1024#256 kb


  def __getKey(self, value):
    # Retorna o SHA-1 do valor
    sha = hashlib.sha1()
    sha.update(value)
    return sha.digest()

  def rip(self, arq):
    # Quebra o arquivo em pedacos
    
    fp = open(arq,"r")
    size = getsize(arq)

    # Determina quantos pedacos serao
    num_files = int(ceil(size / float(self.slice_size)))

    # Retorna um par por vez
    for i in range(num_files):
      value = fp.read(self.slice_size)
      key=self.__getKey(value)
      yield (key, value)
      
    fp.close()

class EntangledViewer(gtk.DrawingArea):
    def __init__(self, node, *args, **kwargs):
        gtk.DrawingArea.__init__(self, *args, **kwargs)
        self.node = node
        self.timeoutID = gobject.timeout_add(5000, self.timeout)
        self.comms = {}
        self.incomingComms = {}
        # poison the node with our GUI hooks
        self.node._protocol.__gui = self
        self.node._protocol.__realSendRPC = self.node._protocol.sendRPC
        self.node._protocol.sendRPC = self.__guiSendRPC
    
        self.node._protocol.__realDatagramReceived = self.node._protocol.datagramReceived
        self.node._protocol.datagramReceived = self.__guiDatagramReceived
        self.msgCounter = 0
        self.printMsgCount = False
        
    def __guiSendRPC(self, contact, method, args, rawResponse=False):
        self.drawComms(contact.id, method)
        self.msgCounter += 1
        return self.node._protocol.__realSendRPC(contact, method, args, rawResponse)
    
    def __guiDatagramReceived(self, datagram, address):
        msgPrimitive = self.node._protocol._encoder.decode(datagram)
        message = self.node._protocol._translator.fromPrimitive(msgPrimitive)
        if isinstance(message, entangled.kademlia.msgtypes.ErrorMessage):
            msg = 'error'
        elif isinstance(message, entangled.kademlia.msgtypes.ResponseMessage):
            msg = 'response'
        else:
            msg = message.request
        self.drawIncomingComms(message.nodeID, msg)
        return self.node._protocol.__realDatagramReceived(datagram, address)
    
    # Draw in response to an expose-event
    __gsignals__ = { "expose-event": "override" }
    
    # Handle the expose-event by drawing
    def do_expose_event(self, event):
        # Create the cairo context
        cr = self.window.cairo_create()
        # Restrict Cairo to the exposed area; avoid extra work
        cr.rectangle(event.area.x, event.area.y,
                event.area.width, event.area.height)
        cr.clip()

        self.draw(cr, *self.window.get_size())
    
    def draw(self, cr, width, height):
        # draw a rectangle for the background            
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        # a circle for the local node
        cr.set_source_rgb(1.0, 0.0, 0.0)
        radius = min(width/5, height/5)
        
        w = width/2
        h = height/2
        s = radius / 2.0 - 20
        radial = cairo.RadialGradient(w/2, h/2, s, w+w/2, h+h/2, s)
        radial.add_color_stop_rgb(0,  0.6, 0, 0.2)
        radial.add_color_stop_rgb(1,  0.1, 0.2, 0.9)
        
        cr.arc(w, h, s, 0, 2 * math.pi)
        cr.set_source(radial)
        cr.fill()
        
        if len(self.comms):
            cr.set_line_width(5)
            cr.set_source_rgba(0, 0.7, 0.8, 0.5)
        else:
            cr.set_source_rgba(0.0, 0.0, 0.4, 0.7)
        cr.arc(w, h, s+1, 0, 2 * math.pi)
        
        cr.stroke()
        cr.set_line_width(2)
        
        blips = []
        kbucket = {}
        for i in range(len(self.node._routingTable._buckets)):
            for contact in self.node._routingTable._buckets[i]._contacts:    
                blips.append(contact)
                kbucket[contact.id] = i
        # ...and now circles for all the other nodes
        if len(blips) == 0:
            spacing = 180
        else:
            spacing = 360/(len(blips))
        degrees = 0
        radius = min(width/6, height/6) / 3 - 20
        if radius < 5:
            radius = 5
        r = width/2.5
        for blip in blips:
            x = r * math.cos(degrees * math.pi/180)
            y = r * math.sin(degrees * math.pi/180)    

            w = width/2 + x
            h = height/2 + y
            if w < 0:
                w = radius
            elif w > width:
                w = width-radius
            if h < 0:
                h = radius
            elif h > height:
                h = height - radius
                

            radial = cairo.RadialGradient(w-w/2, h-h/2, 5, w+w/2, h+h/2, 10)
            radial.add_color_stop_rgb(0,  0.4, 1, 0)
            radial.add_color_stop_rgb(1,  1, 0, 0)
            cr.arc(w, h, radius, 0, 2 * math.pi)
            cr.set_source(radial)
            cr.fill()
            
            cr.set_source_rgb(0.2,0.2,0.2)
            cr.set_font_size(12.0)
            cr.move_to(w+radius+5, h-10)
            cr.set_font_size(12.0)
            cr.show_text(blip.address)
            cr.move_to(w+radius+5, h+5)
            cr.show_text(str(blip.port))
            cr.set_source_rgb(1,1,1)
            
            cr.set_font_size(8.0)
            cr.set_source_rgb(0.4,0.4,0.4)
            cr.move_to(w+radius+5, h+17)
            cr.show_text('k-bucket: %d' % kbucket[blip.id])
            cr.set_font_size(14.0)
            cr.stroke()
            
            if blip.id in self.incomingComms:
                cr.set_source_rgba(0.8, 0.0, 0.0, 0.6) 
                cr.move_to(width/2, height/2)
                cr.line_to(w, h)
                cr.stroke()
                
                cr.move_to(width/2+x/3, height/2+y/3)
                cr.show_text(self.incomingComms[blip.id])
                cr.stroke()
                cr.set_line_width(5)
            
            else:
                cr.set_source_rgba(0.4, 0.0, 0.0, 0.7)
                
            cr.arc(w, h, radius+1, 0, 2 * math.pi)
            cr.stroke()
             
            if blip.id in self.comms:
                cr.set_line_width(5)
                cr.set_source_rgba(0.0, 0.7, 0.8, 0.4)
                cr.move_to(width/2, height/2)
                cr.line_to(w, h)
                cr.stroke()
                
                cr.set_source_rgba(0.0, 0.3, 0.8, 0.7)
                cr.move_to(width/2+x/1.2, height/2+y/1.2)
                cr.show_text(self.comms[blip.id])
                cr.stroke()
            cr.set_line_width(2)
            degrees += spacing
        
        cr.set_line_width(5)
        cr.set_source_rgba(0.6, 0.6, 0.6, 0.4)
        i = 0
        for lostComm in self.comms:
            if lostComm not in blips:
                cr.move_to(width/2, height/2)
                cr.line_to(100*i, 0)
                cr.stroke()
            i += 1
        
        if self.printMsgCount == True:
            cr.set_source_rgb(0.2,0.2,0.2)
            cr.set_font_size(12.0)
            cr.move_to(20, 20)
            cr.show_text('Messages sent: %d' % self.msgCounter)
            cr.stroke()   

    def timeout(self):
        """ Timeout handler to update the GUI """
        #print 'timeout'
        self.window.invalidate_rect(self.allocation, False)
        return True
    
    def drawMsgCounter(self):
        self.printMsgCount = True
        gobject.timeout_add(3000, self.removeMsgCount)
        
    def drawComms(self, contactID, msg):
        if contactID not in self.comms:
            self.comms[contactID] = msg
            gobject.timeout_add(750, self.removeComm, contactID)
            self.window.invalidate_rect(self.allocation, False)
    
    def drawIncomingComms(self, contactID, msg):
        if contactID not in self.incomingComms:
            self.incomingComms[contactID] = msg
            gobject.timeout_add(750, self.removeIncomingComm, contactID)
            self.window.invalidate_rect(self.allocation, False)
    
    def removeIncomingComm(self, contactID):
        try:
            del self.incomingComms[contactID]
        finally:
            self.window.invalidate_rect(self.allocation, False)
            return False
    
    def removeComm(self, contactID):
        try:
            del self.comms[contactID]
        finally:
            self.window.invalidate_rect(self.allocation, False)
            return False
        
    def removeMsgCount(self):
        if self.printMsgCount == True:
            self.printMsgCount = False
            self.msgCounter = 0
            self.window.invalidate_rect(self.allocation, False)
        return False
        
class EntangledViewerWindow(gtk.Window):
    def __init__(self, node):
        gtk.Window.__init__(self)
        
        self.node = node
        self.connect("delete-event", gtk.main_quit)
        
        # Cria Janela
        vbox = gtk.VBox(spacing=3)
        self.add(vbox)
        vbox.show()
    
        # Adiciona grafico de monitoramento
        self.viewer = EntangledViewer(node)
        self.viewer.show()
        vbox.pack_start(self.viewer)
    
        # Adiciona controles (onde ficam as abas)
        notebook = gtk.Notebook()
        notebook.set_tab_pos(pos=gtk.POS_TOP)
        notebook.show()
        vbox.pack_start(notebook,expand=False, fill=False)
        
        ##############################################################
        # Aba Armazenamento de Arquivos
        uploadVbox = gtk.VBox(spacing=3)
        uploadVbox.show()
        notebook.append_page(uploadVbox, gtk.Label('Armazenamento de Arquivos'))


        # Upload
        hbox = gtk.HBox(False, 8)
        hbox.show()

        label = gtk.Label("Arquivo")
        hbox.pack_start(label, False, False, 0)
        label.show()
        eArquivo = gtk.Entry()
        hbox.pack_start(eArquivo, expand=True, fill=True)
        eArquivo.show()

        bArquivo = gtk.Button('Escolher Arquivo')
        hbox.pack_start(bArquivo, expand=False, fill=False)
        bArquivo.connect("clicked", self.escolherArquivo, eArquivo)
        bArquivo.show()

        # Adiciona caixa horizontal com nome do arquivo
        uploadVbox.pack_start(hbox, expand=False, fill=False)


        # Cria tabela para formatar o formulario Catalogo
        table_layout = gtk.Table(rows=5, columns=4, homogeneous=False)

        # Adiciona o Formulario a sua posicao na tabela
        label = gtk.Label("Title")
        label.show()
        table_layout.attach(label, 0, 1, 0, 1, 0,0,0,0)
        eTitle = gtk.Entry()
        eTitle.show()
        table_layout.attach(eTitle, 1, 2, 0, 1, 0,0,0,0)

        label = gtk.Label("Subject")
        label.show()
        table_layout.attach(label, 0, 1, 1, 2, 0,0,0,0)
        eSubject = gtk.Entry()
        eSubject.show()
        table_layout.attach(eSubject, 1, 2, 1, 2, 0,0,0,0)

        label = gtk.Label("Description")
        label.show()
        table_layout.attach(label, 0, 1, 2, 3, 0,0,0,0)
        eDescription = gtk.Entry()
        eDescription.show()
        table_layout.attach(eDescription, 1, 2, 2, 3, 0,0,0,0)
        
        label = gtk.Label("Type")
        label.show()
        table_layout.attach(label, 0, 1, 3, 4, 0,0,0,0)
        eType = gtk.Entry()
        eType.show()
        table_layout.attach(eType, 1, 2, 3, 4, 0,0,0,0)

        label = gtk.Label("RightsHolder")
        label.show()
        table_layout.attach(label, 0, 1, 4, 5, 0,0,0,0)
        eRightsHolder = gtk.Entry()
        eRightsHolder.show()
        table_layout.attach(eRightsHolder, 1, 2, 4, 5, 0,0,0,0)

        label = gtk.Label("Creator")
        table_layout.attach(label, 2, 3, 0, 1, 0,0,0,0)
        label.show()
        eCreator = gtk.Entry()
        eCreator.show()
        table_layout.attach(eCreator, 3, 4, 0, 1, 0,0,0,0)

        label = gtk.Label("Publisher")
        label.show()
        table_layout.attach(label, 2, 3, 1, 2, 0,0,0,0)
        ePublisher = gtk.Entry()
        ePublisher.show()
        table_layout.attach(ePublisher, 3, 4, 1, 2, 0,0,0,0)

        label = gtk.Label("Date")
        table_layout.attach(label, 2, 3, 2, 3, 0,0,0,0)
        label.show()
        eDate = gtk.Entry()
        eDate.show()
        table_layout.attach(eDate, 3, 4, 2, 3, 0,0,0,0)

        label = gtk.Label("Language")
        table_layout.attach(label, 2, 3, 3, 4, 0,0,0,0)
        label.show()
        eLanguage = gtk.Entry()
        eLanguage.show()
        table_layout.attach(eLanguage, 3, 4, 3, 4, 0,0,0,0)

        label = gtk.Label("Identifier")
        table_layout.attach(label, 2, 3, 4, 5, 0,0,0,0)
        label.show()
        eIdentifier = gtk.Entry()
        eIdentifier.show()
        table_layout.attach(eIdentifier, 3, 4, 4, 5, 0,0,0,0)

        # Caixa para catalogo e botao de pesquisa
        hbox = gtk.HBox(False, 8)
        hbox.show()
        uploadVbox.add(hbox)

        # Frame de Catalogo
        frame = gtk.Frame()
        frame.set_label('Catalogo')
        frame.show()
        hbox.pack_start(frame)

        # Imprime a tabela
        table_layout.show()
        frame.add(table_layout)
        
        # Botao de Upload (envia dados para a DHT)
        bUpload = gtk.Button('Upload')
        hbox.pack_start(bUpload, expand=False, fill=True)
        bUpload.connect("clicked", self.upload, eArquivo, eTitle, eSubject, eDescription, eType, eRightsHolder, eCreator, ePublisher, eDate, eLanguage, eIdentifier)
        bUpload.show()
        

        ##############################################################
        # Aba Busca de Arquivos
        searchVbox = gtk.VBox(spacing=3)
        searchVbox.show()
        notebook.append_page(searchVbox, gtk.Label('Busca de Arquivos'))
        

        # Search for keyword
        hbox = gtk.HBox(False, 8)
        hbox.show()

        # Label e textbox para pesquisa
        label = gtk.Label("Palavra Chave:")
        hbox.pack_start(label, False, False, 0)
        label.show()
        entryKeyword = gtk.Entry()
        hbox.pack_start(entryKeyword, expand=True, fill=True)
        entryKeyword.show()
       
        # Botao Pesquisar
        button = gtk.Button('Pesquisar')
        hbox.pack_start(button, expand=False, fill=False)
        button.connect("clicked", self.search, entryKeyword)
        button.show()
        searchVbox.pack_start(hbox, expand=False, fill=False)

        # Frame do Resultado
        frame = gtk.Frame()
        frame.set_label('Resultado da Busca')
        frame.show()
        searchVbox.pack_start(frame)

        # Janela com Scroll
        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        frame.add(sw)
        sw.show()

        # Create tree model
        model = self.createListStore([])

        # Create tree view
        self.dhtTreeView = gtk.TreeView(model)
        self.dhtTreeView.set_rules_hint(True)
        self.dhtTreeView.set_search_column(0)
        self.dhtTreeView.connect('row-activated', self.downloadFile)
        # Add the tree view to the scrolling window
        sw.add(self.dhtTreeView)
        self.dhtTreeView.show()
        # column for file name/description
        column = gtk.TreeViewColumn('Resultado:', gtk.CellRendererText(), text=0)
        column.set_sort_column_id(0)
        self.dhtTreeView.append_column(column)

    # Cria lista com resultados para preencher o 'model'
    def createListStore(self, data):
        lstore = gtk.ListStore(gobject.TYPE_STRING)
        for item in data:
            iter = lstore.append()
            lstore.set(iter, 0, item)
        return lstore

    # Abre caixa para selecionar o arquivo e retorna seu path em 'arquivo'
    def escolherArquivo(self, sender, arquivo):
        fd = gtk.FileChooserDialog(title='Escolha um arquivo', action=gtk.FILE_CHOOSER_ACTION_OPEN, buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OK,gtk.RESPONSE_OK))
        fd.set_default_response(gtk.RESPONSE_OK)
        response = fd.run()
        if response == gtk.RESPONSE_OK:
            arquivo.set_text(fd.get_filename())
        fd.destroy()

    # Botao de upload da primeira aba
    def upload(self, sender, eArquivo, eTitle, eSubject, eDescription, eType, eRightsHolder, eCreator, ePublisher, eDate, eLanguage, eIdentifier):
        arquivo = eArquivo.get_text()

        catalogo = {
            "Title" : eTitle.get_text(),
            "Subject" : eSubject.get_text(),
            "Description" : eDescription.get_text(),
            "Type" : eType.get_text(),
            "RightsHolder" : eRightsHolder.get_text(),
            "Creator" : eCreator.get_text(),
            "Publisher" : ePublisher.get_text(),
            "Date" : eDate.get_text(),
            "Language" : eLanguage.get_text(),
            "Identifier" : eIdentifier.get_text()
        }

        # Adiciona arquivo em pedacos na DHT e guarda as chaves deles em partsKey
        split = SplitFile()
        partsKey = []
        for piece in split.rip(arquivo):
            hKey = piece[0]
            value = piece[1]
            self.storeValue(self,hKey, value)
            partsKey.append(hKey)

        # Publica paravras chave do catalogo e a referencia aos pedacos do arquivo
        self.publishData(self, str(catalogo), str(partsKey))

    # Botao Pesquisar da segunda aba
    def search(self, sender, entryKeyword):
        sender.set_sensitive(False)
        keyword = entryKeyword.get_text()
        entryKeyword.set_sensitive(False)
        def gotValue(result):
            sender.set_sensitive(True)
            entryKeyword.set_sensitive(True)
            model = self.createListStore(result)
            self.dhtTreeView.set_model(model)
        def error(failure):
            print 'GUI: an error occurred:', failure.getErrorMessage()
            sender.set_sensitive(True)
            entryKeyword.set_sensitive(True)
        df = self.node.searchForKeywords(keyword)
        df.addCallback(gotValue)
        df.addErrback(error)

    # Duplo clique na lista de resultados
    def downloadFile(self, treeView, path, column):
        # Obtem a string clicada no menu
        model = treeView.get_model()
        iter = model.get_iter(path)
        catalogo = model.get(iter, 0)[0]
     
        # O entedeco dos pedacos esta no valor de um registro cuja chave e o hash do catalogo e a chave
        h = hashlib.sha1()
        h.update(catalogo)
        hKey = h.digest()
        
        # Buffer parcial para obter o arquivo
        self.buffer = ''

        # Obter o valor dos pedacos e os salva em um Buffer parcial
        def getValue(result):
            self.viewer.printMsgCount = True
            for dados in result.values():
                self.buffer += str(dados)

        # Percorre pedacos e passa para obter o valor dos mesmo
        def showValue(result):
            self.viewer.printMsgCount = True
            for items in result.values():
                for item in eval(items):
                    df1 = self.node.iterativeFindValue(item)
                    df1.addCallback(getValue)
        
        # Encontra registro que tem as chaves dos pedacos
        df = self.node.iterativeFindValue(hKey)
        df.addCallback(showValue)
 
        # Se tudo deu certo, abre caixa de dialogo para salvar o arquivo
        self.filename = ''
        fd = gtk.FileChooserDialog(title=None, action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                   buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_SAVE,gtk.RESPONSE_OK))
        fd.set_default_response(gtk.RESPONSE_OK)
        fd.set_current_name(self.filename)
        response = fd.run()
        if response == gtk.RESPONSE_OK:
            destfilename = fd.get_filename()
            f = open(destfilename, 'w')
            f.write(self.buffer)
            f.close()
        fd.destroy()


    # Publica valores na DHT e permite busca pelo catalogo (ver catalogo em upload)
    def publishData(self, sender, name, value):
        self.viewer.msgCounter = 0
        self.viewer.printMsgCount = False
        def completed(result):
            self.viewer.printMsgCount = True
        df = self.node.publishData(name, value)
        df.addCallback(completed)

    # Utilizado para armazenar uma chave/valor na DHT
    def storeValue(self, sender, hKey, value):
        self.viewer.msgCounter = 0
        self.viewer.printMsgCount = False
        
        def completed(result):
            self.viewer.printMsgCount = True
        df = self.node.iterativeStore(hKey, value)
        df.addCallback(completed)


if __name__ == '__main__':
    #O trabalho assume que a rede e acessada apenas localmente, ou seja,
    # os IPs de todos os nos sao 127.0.0.1, variando apenas a porta
    ip_padrao = "127.0.0.1"
    porta_padrao = 4000

    #Verifica se foi chamado com a sintaxe correta
    if len(sys.argv) > 2:
        print 'Uso:\n%s <UDP_PORT>' % sys.argv[0]
        sys.exit(1)
    if len(sys.argv) == 2:
        try:
            int(sys.argv[1])
        except ValueError:
            print 'UDP_PORT precisa ser um valor inteiro (por exemplo 4001)'
            print 'Uso:\n%s <UDP_PORT>' % sys.argv[0]
            sys.exit(1)
        knownNodes = [(ip_padrao, porta_padrao)]
        porta = int(sys.argv[1])
    else:
        knownNodes = None
        porta = porta_padrao


    dataStore = None
    #dataStore = SQLiteDataStore(dataDir + '/%s.sqlite' % porta)

    if dataStore != None:
        #Verifica se pode criar o diretorio para armazenar os dados
        dataDir = os.path.abspath('.')+'/store'
        try:
            os.makedirs(dataDir)
        except OSError:
            pass #A funcao cria se o diretorio nao existir...
            #print 'Nao foi possivel criar o diretorio %s' % dataDir
            #sys.exit(1)

    node = entangled.node.EntangledNode(udpPort=porta, dataStore=dataStore)
    
    window = EntangledViewerWindow(node)

    window.set_default_size(640, 640)
    window.set_title('Trabalho de BDD - porta %s' % porta)

    window.present()
    
    node.joinNetwork(knownNodes)
    twisted.internet.reactor.run()