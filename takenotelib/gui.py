
import sys, os, tempfile, re

# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk

# takenote imports
import takenotelib as takenote
from takenotelib.undo import UndoStack
from takenotelib.richtext import RichTextView, RichTextImage


# TODO: shade undo/redo


class TakeNoteTreeView (object):
    
    def __init__(self):
        self.on_select_node = None
    
        # create a TreeStore with one string column to use as the model
        self.treestore = gtk.TreeStore(gdk.Pixbuf, str, object)
                
        # create the TreeView using treestore
        self.treeview = gtk.TreeView(self.treestore)
        self.treeview.connect("key-release-event", self.on_key_released)
        #self.treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.treeview.get_selection().set_select_function(self.on_select)#, full=True)
        self.treeview.set_headers_visible(False)

        # create the TreeViewColumn to display the data
        self.tvcolumn = gtk.TreeViewColumn()
        self.tvcolumn.set_clickable(False)

        # add tvcolumn to treeview        
        self.treeview.append_column(self.tvcolumn)

        # create a CellRendererText to render the data
        self.cell_icon = gtk.CellRendererPixbuf()
        self.cell_text = gtk.CellRendererText()
        self.cell_text.connect("edited", self.on_edit_title)
        self.cell_text.set_property("editable", True)        

        # add the cell to the tvcolumn and allow it to expand
        self.tvcolumn.pack_start(self.cell_icon, False)
        self.tvcolumn.pack_start(self.cell_text, True)

        # map cells to columns in textstore
        self.tvcolumn.add_attribute(self.cell_icon, 'pixbuf', 0)
        self.tvcolumn.add_attribute(self.cell_text, 'text', 1)

        # make it searchable
        self.treeview.set_search_column(1)
        
        # Allow drag and drop reordering of rows
        #self.treeview.set_reorderable(True)
        
        self.icon = pixbuf = gdk.pixbuf_new_from_file("bitmaps/open.xpm")
                
    
    #def on_activate(self, treeview, path, view_column):
    #    print path, view_column

    
    def on_key_released(self, widget, event):
        if event.keyval == gdk.keyval_from_name("Delete"):
            self.on_delete_node()
            self.treeview.stop_emission("key-release-event")
            

    def on_edit_title(self, cellrenderertext, path, new_text):
        try:
            node = self.get_node(path)        
            node.rename(new_text)
            
            self.treestore[path][1] = new_text
        except Exception, e:
            print e
            print "takenote: could not rename '%s'" % node.title
    
    
    def edit_node(self, node):
        path = self.get_path(node)
        self.treeview.set_cursor_on_cell(path, self.tvcolumn, self.cell_text, 
                                         True)

    
    def expand_node(self, node):
        path = self.get_path(node)
        self.treeview.expand_to_path(path)
        

    def on_select(self, path):
        
        model, it = self.treeview.get_selection().get_selected()
        is_selected = (it == None)
        
        if is_selected and self.on_select_node:
            self.on_select_node(self.get_node(path))
        return True


    
    def set_notebook(self, notebook):
        self.notebook = notebook
        
        if self.notebook is None:
            self.treestore.clear()
        
        else:
            root = self.notebook.get_root_node()
            self.add_node(None, root)
        
    
    def add_node(self, parent, node):
        it = self.treestore.append(parent, [self.icon, node.get_title(), node])
        
        for child in node.get_children():
            self.add_node(it, child)
    
    
    def update_node(self, node):
        path = self.get_path(node)
        
        for child in self.treestore[path].iterchildren():
            self.treestore.remove(child.iter)
        
        it = self.treestore.get_iter(path)
        for child in node.get_children():
            self.add_node(it, child)
    
    
    def on_delete_node(self):
        
        model, it = self.treeview.get_selection().get_selected()
        node = self.get_node(model.get_path(it))
        parent = node.get_parent()
        
        if parent != None:
            node.delete()
            self.update_node(parent)
        else:
            # warn
            print "Cannot delete notebook's toplevel directory"
        
    
    def get_path(self, node):
        ancestors = []
        ptr = node
        while ptr != None:
            ancestors.append(ptr)
            ptr = ptr.get_parent()
        ancestors.pop()
        
        
        path = [0]
        ptr = self.treestore[0]
        for node in reversed(ancestors):
            for i, row in enumerate(ptr.iterchildren()):
                if row[2] == node:
                    path.append(i)
                    ptr = row
                    break
        
        return tuple(path)
        

    def get_node(self, path):
        
        return self.treestore[path][2]
        
                    



class TakeNoteSelector (object):
    
    def __init__(self):
        self.on_select_node = None
        self.sel_nodes = None
        
        # Create a new scrolled window, with scrollbars only if needed
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        self.model = gtk.ListStore(gdk.Pixbuf, gobject.TYPE_STRING, object)
        self.treeview = gtk.TreeView(self.model)
        self.treeview.connect("key-release-event", self.on_key_released)
        scrolled_window.add_with_viewport (self.treeview)
        self.treeview.show()
        self.treeview.get_selection().set_select_function(self.on_select)
        
        cell_icon = gtk.CellRendererPixbuf()
        self.cell_text = gtk.CellRendererText()
        self.column = gtk.TreeViewColumn()
        self.column.set_title("Pages")
        self.treeview.append_column(self.column)
        
        self.column.pack_start(cell_icon, False)
        self.column.pack_start(self.cell_text, True)
        self.cell_text.connect("edited", self.on_edit_title)
        self.cell_text.set_property("editable", True)

        # map cells to columns in textstore
        self.column.add_attribute(cell_icon, 'pixbuf', 0)
        self.column.add_attribute(self.cell_text, 'text', 1)
        
        self.icon = pixbuf = gdk.pixbuf_new_from_file("bitmaps/copy.xpm")
        self.view = scrolled_window


    def on_edit_title(self, cellrenderertext, path, new_text):
        try:
            page = self.get_page(path)        
            page.rename(new_text)
            
            self.model[path][1] = new_text
        except Exception, e:
            print e
            print "takenote: could not rename page '%s'" % node.title
    
    def edit_node(self, page):
        path = self.get_path(page)
        self.treeview.set_cursor_on_cell(path, self.column, self.cell_text, 
                                         True)

    
    def on_key_released(self, widget, event):
        if event.keyval == gdk.keyval_from_name("Delete"):
            self.on_delete_page()
            self.treeview.stop_emission("key-release-event")
    
    
    def view_nodes(self, nodes):
        self.sel_nodes = nodes
        self.model.clear()
        
        for node in nodes:
            for page in node.get_pages():
                it = self.model.append()
                self.model.set(it, 0, self.icon)                
                self.model.set(it, 1, page.get_title())
                self.model.set(it, 2, page)
        
        self.on_select_node(None)

    
    def update(self):
        self.view_nodes(self.sel_nodes)
    
    def select_pages(self, pages):
        page = pages[0]
        path = self.get_path(page)
        if path != None:
            self.treeview.set_cursor_on_cell(path)
        
    
    def on_select(self, path): 

        model, it = self.treeview.get_selection().get_selected()
        is_selected = (it == None)
        
        if is_selected and self.on_select_node:
            self.on_select_node(self.get_page(path))
        else:
            self.on_select_node(None)
        return True
    
    
    def on_delete_page(self):
        model, it = self.treeview.get_selection().get_selected()
        page = self.get_page(model.get_path(it))
        page.delete()
        self.update()


    
    def set_notebook(self, notebook):
        self.notebook = notebook
        
        if self.notebook is None:
            self.model.clear()
        
    
    def get_page(self, path):
        return self.model[path[0]][2]
    
    
    def get_path(self, page):
        for i, row in enumerate(self.model):
            if row[2] == page:
                return (i,)
        return None


class TakeNoteEditor (object):

    def __init__(self):
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.textview = RichTextView()
        sw.add(self.textview)
        sw.show()
        self.textview.show()
        self.view = sw
        
        self.page = None
        
    def view_page(self, page):
        self.save()
        self.page = page
        
        if page is None:
            self.textview.disable()
        else:
            self.textview.enable()
            self.textview.load(page.get_data_file())
    
    def save(self):
        # TODO: make sure note is not deleted
        if self.page is not None:
            self.textview.save(self.page.get_data_file())


class TakeNoteWindow (gtk.Window):
    def __init__(self):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        
        self.set_title("TakeNote")
        self.set_default_size(800, 600)
        self.connect("destroy", lambda w: self.on_close())
        
        self.notebook = None
        self.sel_nodes = []
        self.current_page = None
        
        # selector
        self.selector = TakeNoteSelector()
        self.selector.on_select_node = self.on_select_page
        
        # treeview
        self.treeview = TakeNoteTreeView()
        self.treeview.on_select_node = self.on_select_treenode
        
        # editor
        self.editor = TakeNoteEditor()
        self.editor.textview.font_callback = self.on_font_change
        self.editor.view_page(None)
        
        #====================================
        # Layout
        # vertical box
        main_vbox = gtk.VBox(False, 0)
        self.add(main_vbox)
        
        # menu bar
        main_vbox.set_border_width(1)
        menubar = self.make_menubar()
        main_vbox.pack_start(menubar, False, True, 0)
        
        # toolbar
        #handlebox = gtk.HandleBox()
        #handlebox.add(self.make_toolbar())
        main_vbox.pack_start(self.make_toolbar(), False, True, 0)          
        
        
        #==========================================
        # create a horizontal paned widget
        hpaned = gtk.HPaned()
        main_vbox.pack_start(hpaned, True, True, 0)
        hpaned.set_position(200)

        # create a vertical paned widget
        vpaned = gtk.VPaned()
        hpaned.add2(vpaned)
        vpaned.set_position(200)
        
        
        # status bar
        self.status_bar = gtk.Statusbar()      
        main_vbox.pack_start(self.status_bar, False, True, 0)  


        # layout major widgets
        hpaned.add1(self.treeview.treeview)
        vpaned.add1(self.selector.view)        
        vpaned.add2(self.editor.view)
        
        
        self.show_all()        
        self.treeview.treeview.grab_focus()
        

    def on_new_notebook(self):
        self.filew = gtk.FileSelection("New notebook")
        self.filew.ok_button.connect("clicked", self.on_new_notebook_ok)
        self.filew.cancel_button.connect("clicked",
                                         lambda w: self.filew.destroy())
        self.filew.show()

    def on_new_notebook_ok(self, w):
        filename = self.filew.get_filename()
        self.filew.destroy()
        self.new_notebook(filename)

    def on_open_notebook(self):
        self.filew = gtk.FileSelection("Open notebook")
        #self.filew = gtk.FileChooserDialog("Open notebook")
        
        self.filew.ok_button.connect("clicked", self.on_open_notebook_ok)
        self.filew.cancel_button.connect("clicked",
                                         lambda w: self.filew.destroy())
        self.filew.show()
    
    
    def on_open_notebook_ok(self, w):
        filename = self.filew.get_filename()
        self.filew.destroy()
        self.open_notebook(filename)
        
    
    def new_notebook(self, filename):
        if self.notebook is not None:
            self.close_notebook()
        
        try:
            self.notebook = takenote.NoteBook(filename)
            self.notebook.create()
        except Exception, e:
            self.notebook = None
            print e
            print "could not create new notebook"
        
        self.open_notebook(filename)
        
        
    
    def open_notebook(self, filename):
        if self.notebook is not None:
            self.close_notebook()
        self.notebook = takenote.NoteBook(filename)
        self.selector.set_notebook(self.notebook)
        self.treeview.set_notebook(self.notebook)
        self.treeview.treeview.expand_all()
        self.treeview.treeview.grab_focus()
        
        
    def close_notebook(self):
        if self.notebook is not None:
            self.editor.save()
            self.notebook = None
            self.selector.set_notebook(self.notebook)
            self.treeview.set_notebook(self.notebook)
    
    
    def on_new_dir(self):
        if len(self.sel_nodes) == 1:
            parent = self.sel_nodes[0]
        else:
            parent = self.notebook.get_root_node()
        
        node = parent.new_dir("New Node")
        self.treeview.update_node(parent)
        self.treeview.expand_node(parent)
        self.treeview.edit_node(node)
    
    
    def on_new_page(self):
        if len(self.sel_nodes) == 1:
            parent = self.sel_nodes[0]
        else:
            parent = self.notebook.get_root_node()
        
        node = parent.new_page("New Page")
        self.treeview.update_node(parent)
        self.selector.update()
        #self.selector.select_pages([node])
        self.selector.edit_node(node)
        #self.editor.textview.grab_focus()
    
    
    
    def on_close(self):
        """close the window and quit"""
        self.close_notebook()
        gtk.main_quit()
        return False
    
    
    def on_select_treenode(self, node):
        self.sel_nodes = [node]
        self.selector.view_nodes([node])
    
    def on_select_page(self, page):
        self.current_page = page
        self.editor.view_page(page)
        #self.editor.textview.grab_focus()
    
    
    #=============================================================
    # Font UI Update
    
    def on_font_change(self, mods, justify):
    
        # block toolbar handlers
        self.bold_button.handler_block(self.bold_id)
        self.italic_button.handler_block(self.italic_id)
        self.underline_button.handler_block(self.underline_id) 
        self.left_button.handler_block(self.left_id)
        self.center_button.handler_block(self.center_id)
        self.right_button.handler_block(self.right_id) 
        
        # update font mods
        self.bold_button.set_active(mods["bold"])
        self.italic_button.set_active(mods["italic"])        
        self.underline_button.set_active(mods["underline"])
        
        # update text justification
        self.left_button.set_active(justify == "left")
        self.center_button.set_active(justify == "center")
        self.right_button.set_active(justify == "right")                
        
        # unblock toolbar handlers
        self.bold_button.handler_unblock(self.bold_id)
        self.italic_button.handler_block(self.italic_id)
        self.underline_button.handler_unblock(self.underline_id)
        self.left_button.handler_unblock(self.left_id)
        self.center_button.handler_unblock(self.center_id)
        self.right_button.handler_unblock(self.right_id) 
        
        
    
    def on_bold(self):
        self.editor.textview.on_bold()
        mods, justify = self.editor.textview.get_font()
        
        self.bold_button.handler_block(self.bold_id)
        self.bold_button.set_active(mods["bold"])
        self.bold_button.handler_unblock(self.bold_id)
    
    
    def on_italic(self):
        self.editor.textview.on_italic()
        mods, justify = self.editor.textview.get_font()
        
        self.italic_button.handler_block(self.italic_id)
        self.italic_button.set_active(mods["italic"])
        self.italic_button.handler_block(self.italic_id)
    
    
    def on_underline(self):
        self.editor.textview.on_underline()
        mods, justify = self.editor.textview.get_font()
        
        self.underline_button.handler_block(self.underline_id)        
        self.underline_button.set_active(mods["underline"])
        self.underline_button.handler_unblock(self.underline_id)
    

    def on_left_justify(self):
        self.editor.textview.on_left_justify()
        mods, justify = self.editor.textview.get_font()
        self.on_font_change(mods, justify)

    def on_center_justify(self):
        self.editor.textview.on_center_justify()
        mods, justify = self.editor.textview.get_font()
        self.on_font_change(mods, justify)

    def on_right_justify(self):
        self.editor.textview.on_right_justify()
        mods, justify = self.editor.textview.get_font()
        self.on_font_change(mods, justify)


    def on_screenshot(self):
        if self.current_page == None:
            return
    
        f, imgfile = tempfile.mkstemp(".xpm", "takenote")
        os.close(f)
    
        os.system("import %s" % imgfile)
        if os.path.exists(imgfile):
            try:
                pixbuf = gdk.pixbuf_new_from_file(imgfile)
                img = RichTextImage()
                img.set_from_pixbuf(pixbuf)
                self.editor.textview.insert_image(img, "screenshot.jpg")
            except Exception, e:
                print e
                print "error reading screenshot '%s'" % imgfile
            
            os.remove(imgfile)        

    def on_choose_font(self):
        self.font_sel.clicked()
    
    
    def on_font_set(self):
        self.editor.textview.on_font_set(self.font_sel)
        self.editor.textview.grab_focus()
    
    
    def on_goto_treeview(self):
        self.treeview.treeview.grab_focus()
        
    def on_goto_listview(self):
        self.selector.treeview.grab_focus()
        
    def on_goto_editor(self):
        self.editor.textview.grab_focus()
    
    
    #================================================
    # Menubar
    
    def make_menubar(self):
        # menu bar
        self.menu_items = (
            ("/_File",               
                None, None, 0, "<Branch>"),
            ("/File/_New Notebook",
                None, lambda w,e: self.on_new_notebook(), 0, None),
            ("/File/New _Page",      
                "<control>N", lambda w,e: self.on_new_page(), 0, None),
            ("/File/New _Directory", 
                "<control><shift>N", lambda w,e: self.on_new_dir(), 0, None),
            ("/File/_Open",          
                "<control>O", lambda w,e: self.on_open_notebook(), 0, None),
            ("/File/_Save Page",     
                "<control>S", lambda w,e: self.editor.save(), 0, None),
            ("/File/_Close", 
                "<control>W", lambda w, e: self.close_notebook(), 0, None),
            ("/File/sep1", 
                None, None, 0, "<Separator>" ),
            ("/File/Quit", 
                "<control>Q", lambda w,e: self.on_close(), 0, None),

            ("/_Edit", 
                None, None, 0, "<Branch>"),
            ("/Edit/Un_do",     
                "<control>Z", lambda w,e: self.editor.textview.undo(), 0, None),
            ("/Edit/_Redo", 
                "<control><shift>Z", lambda w,e: self.editor.textview.redo(), 0, None),
            ("/Edit/sep1", 
                None, None, 0, "<Separator>"),
            ("/Edit/Insert Screenshot",
                "<control>Insert", lambda w,e: self.on_screenshot(), 0, None),
            
            ("/_Format", 
                None, None, 0, "<Branch>"),
            ("/Format/_Left Align", 
                "<control>L", lambda w,e: self.on_left_justify(), 0, None ),
            ("/Format/C_enter Align", 
                "<control>E", lambda w,e: self.on_center_justify(), 0, None ),
            ("/Format/_Right Align", 
                "<control>R", lambda w,e: self.on_right_justify(), 0, None ),
            ("/Format/sep1", 
                None, None, 0, "<Separator>" ),            
            ("/Format/_Bold", 
                "<control>B", lambda w,e: self.on_bold(), 0, None ),
            ("/Format/_Italic", 
                "<control>I", lambda w,e: self.on_italic(), 0, None ),
            ("/Format/_Underline", 
                "<control>U", lambda w,e: self.on_underline(), 0, None ),
            ("/Format/sep2", 
                None, None, 0, "<Separator>" ),
            ("/Format/Choose _Font", 
                "<control>F", lambda w, e: self.on_choose_font(), 0, None),
            
            ("/_Go", 
                None, None, 0, "<Branch>"),
            ("/Go/Go To _Tree View",
                "<control>T", lambda w,e: self.on_goto_treeview(), 0, None),
            ("/Go/Go To _List View",
                "<control>Y", lambda w,e: self.on_goto_listview(), 0, None),
            ("/Go/Go To _Editor",
                "<control>D", lambda w,e: self.on_goto_editor(), 0, None),
                
            
            ("/_Help",       None, None, 0, "<LastBranch>" ),
            ("/_Help/About", None, None, 0, None ),
            )    
    
        accel_group = gtk.AccelGroup()

        # This function initializes the item factory.
        # Param 1: The type of menu - can be MenuBar, Menu,
        #          or OptionMenu.
        # Param 2: The path of the menu.
        # Param 3: A reference to an AccelGroup. The item factory sets up
        #          the accelerator table while generating menus.
        item_factory = gtk.ItemFactory(gtk.MenuBar, "<main>", accel_group)

        # This method generates the menu items. Pass to the item factory
        #  the list of menu items
        item_factory.create_items(self.menu_items)

        # Attach the new accelerator group to the window.
        self.add_accel_group(accel_group)

        # need to keep a reference to item_factory to prevent its destruction
        self.item_factory = item_factory
        # Finally, return the actual menu bar created by the item factory.
        return item_factory.get_widget("<main>")


    def make_toolbar(self):
        
        toolbar = gtk.Toolbar()
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        toolbar.set_style(gtk.TOOLBAR_ICONS)
        toolbar.set_border_width(0)
        
        
        # bold tool
        icon = gtk.Image() # icon widget
        icon.set_from_file("bitmaps/bold.xpm")
        self.bold_button = gtk.ToggleToolButton()
        self.bold_button.set_icon_widget(icon)
        #self.bold_button.set_tooltip_text("Bold")
        self.bold_id = self.bold_button.connect("toggled", lambda w: self.editor.textview.on_bold())
        toolbar.insert(self.bold_button, -1)


        # italic tool
        icon = gtk.Image() # icon widget
        icon.set_from_file("bitmaps/italic.xpm")
        self.italic_button = gtk.ToggleToolButton()
        self.italic_button.set_icon_widget(icon)
        #self.italic_button.set_tooltip_text("Italic")
        self.italic_id = self.italic_button.connect("toggled", lambda w: self.editor.textview.on_italic())
        toolbar.insert(self.italic_button, -1)

        # underline tool
        icon = gtk.Image() # icon widget
        icon.set_from_file("bitmaps/underline.xpm")
        self.underline_button = gtk.ToggleToolButton()
        self.underline_button.set_icon_widget(icon)
        #self.underline_button.set_tooltip_text("Underline")
        self.underline_id = self.underline_button.connect("toggled", lambda w: self.editor.textview.on_underline())
        toolbar.insert(self.underline_button, -1)
                

        # font button
        self.font_sel = gtk.FontButton()
        item = gtk.ToolItem()
        item.add(self.font_sel)
        #item.set_tooltip_text("Set Font")
        toolbar.insert(item, -1)
        self.font_sel.connect("font-set", lambda w: self.on_font_set())
        
        # left tool
        icon = gtk.Image() # icon widget
        icon.set_from_file("bitmaps/alignleft.xpm")
        self.left_button = gtk.ToggleToolButton()
        self.left_button.set_icon_widget(icon)
        #self.left_button.set_tooltip_text("Left Justify")
        self.left_id = self.left_button.connect("toggled", lambda w: self.editor.textview.on_left_justify())
        toolbar.insert(self.left_button, -1)
        
        # center tool
        icon = gtk.Image() # icon widget
        icon.set_from_file("bitmaps/aligncenter.xpm")
        self.center_button = gtk.ToggleToolButton()
        self.center_button.set_icon_widget(icon)
        #self.center_button.set_tooltip_text("Center Justify")
        self.center_id = self.center_button.connect("toggled", lambda w: self.editor.textview.on_center_justify())
        toolbar.insert(self.center_button, -1)
        
        # right tool
        icon = gtk.Image() # icon widget
        icon.set_from_file("bitmaps/alignright.xpm")
        self.right_button = gtk.ToggleToolButton()
        self.right_button.set_icon_widget(icon)
        #self.right_button.set_tooltip_text("Right Justify")
        self.right_id = self.right_button.connect("toggled", lambda w: self.editor.textview.on_right_justify())
        toolbar.insert(self.right_button, -1)        
        
        return toolbar


class TakeNote (object):
    
    def __init__(self, basedir=""):
        self.window = TakeNoteWindow()
        self.basedir = basedir
        
    def open_notebook(self, filename):
        self.window.open_notebook(filename)

