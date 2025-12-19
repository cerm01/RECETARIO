import sys
import sqlite3
import math
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTableWidget, QTableWidgetItem, QTabWidget, 
                             QComboBox, QMessageBox, QHeaderView, QSplitter,
                             QFormLayout, QGroupBox, QListWidget, QAbstractItemView, 
                             QTextEdit, QDialog, QGridLayout, QFrame)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        try:
            val1 = float(self.text().replace('$', '').replace(',', ''))
            val2 = float(other.text().replace('$', '').replace(',', ''))
            return val1 < val2
        except ValueError:
            return super().__lt__(other)

# Clase para la base de datos
class DataBase:
    def __init__(self, db_name="db_recetario.db"):
        self.conn = sqlite3.connect(db_name)
        self.conn.execute("PRAGMA foreign_keys = 1")
        self.cursor = self.conn.cursor()
        
        self.migracion_inicial()
        self.crear_tablas()

    def migracion_inicial(self):
        # 1. Migración Subcategorías
        try:
            self.cursor.execute("SELECT categoria_id FROM subcategorias LIMIT 1")
        except sqlite3.OperationalError:
            self.cursor.execute("DROP TABLE IF EXISTS subcategorias")
            self.conn.commit()

        # 2. Migración Productos
        try:
            self.cursor.execute("SELECT categoria_id FROM productos LIMIT 1")
        except sqlite3.OperationalError:
            print("Actualizando tabla productos...")
            self.cursor.execute("ALTER TABLE productos ADD COLUMN categoria_id INTEGER REFERENCES categorias(id)")
            self.cursor.execute("ALTER TABLE productos ADD COLUMN subcategoria_id INTEGER REFERENCES subcategorias(id)")
            self.conn.commit()

    def crear_tablas(self):
        # Tablas configuración
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS categorias (id INTEGER PRIMARY KEY, nombre TEXT)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS tamanos (id INTEGER PRIMARY KEY, nombre TEXT)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS unidades (id INTEGER PRIMARY KEY, nombre TEXT)''')
        
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS subcategorias (
            id INTEGER PRIMARY KEY, 
            nombre TEXT,
            categoria_id INTEGER,
            FOREIGN KEY(categoria_id) REFERENCES categorias(id)
        )''')
        
        # Insumos
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS insumos (
            id INTEGER PRIMARY KEY, 
            nombre TEXT, 
            unidad_compra_id INTEGER,
            unidad_uso_id INTEGER,
            cantidad_envase REAL,
            costo_envase REAL,
            factor_conversion REAL,
            rendimiento_total REAL,
            costo_unitario REAL,
            FOREIGN KEY(unidad_compra_id) REFERENCES unidades(id),
            FOREIGN KEY(unidad_uso_id) REFERENCES unidades(id)
        )''')

        # Tabla de productos
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY, 
            nombre TEXT, 
            instrucciones TEXT,
            categoria_id INTEGER,
            subcategoria_id INTEGER,
            FOREIGN KEY(categoria_id) REFERENCES categorias(id),
            FOREIGN KEY(subcategoria_id) REFERENCES subcategorias(id)
        )''')
        
        # Pasos de Receta
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS receta_pasos (
            id INTEGER PRIMARY KEY,
            producto_id INTEGER,
            orden INTEGER,
            descripcion TEXT,
            FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE CASCADE
        )''')

        # Configuración Tamaño
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS receta_config (
            id INTEGER PRIMARY KEY,
            producto_id INTEGER,
            tamano_id INTEGER,
            UNIQUE(producto_id, tamano_id),
            FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE CASCADE,
            FOREIGN KEY(tamano_id) REFERENCES tamanos(id)
        )''')

        # Ingredientes
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS receta_ingredientes (
            receta_config_id INTEGER,
            insumo_id INTEGER,
            cantidad_necesaria REAL,
            FOREIGN KEY(receta_config_id) REFERENCES receta_config(id) ON DELETE CASCADE,
            FOREIGN KEY(insumo_id) REFERENCES insumos(id)
        )''')
        
        # Datos base
        self.cursor.execute("SELECT count(*) FROM unidades")
        if self.cursor.fetchone()[0] == 0:
            unidades_base = ["Pieza", "Litro", "Galón", "Onza (oz)", "Gramo (gr)", "Mililitro (ml)", "Kilogramo (kg)"]
            for u in unidades_base:
                self.cursor.execute("INSERT INTO unidades (nombre) VALUES (?)", (u,))
        
        self.conn.commit()

    def ejecutar(self, query, params=()):
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            return self.cursor
        except sqlite3.Error as e:
            print(f"Error BD: {e}")
            return None

    def traer_datos(self, query, params=()):
        return self.cursor.execute(query, params).fetchall()

# --- CLASES PARA CONFIGURACIÓN (CRUDs) ---

class ABMSimple(QWidget):
    def __init__(self, titulo, tabla, db, callback_cambios=None):
        super().__init__()
        self.tabla_bd = tabla
        self.db = db
        self.id_seleccionado = None
        self.callback_cambios = callback_cambios
        
        layout = QVBoxLayout()
        self.group = QGroupBox(titulo)
        vbox = QVBoxLayout()

        # Formulario
        h_in = QHBoxLayout()
        self.txt_nombre = QLineEdit()
        self.txt_nombre.setPlaceholderText("Nombre...")
        h_in.addWidget(self.txt_nombre)
        vbox.addLayout(h_in)

        # Botones
        h_btns = QHBoxLayout()
        self.btn_add = QPushButton("Agregar")
        self.btn_add.clicked.connect(self.agregar)
        self.btn_update = QPushButton("Actualizar")
        self.btn_update.clicked.connect(self.actualizar)
        self.btn_update.setEnabled(False)
        self.btn_delete = QPushButton("Eliminar")
        self.btn_delete.setStyleSheet("background-color: #dc3545;")
        self.btn_delete.clicked.connect(self.eliminar)
        self.btn_delete.setEnabled(False)
        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.setStyleSheet("background-color: #6c757d;")
        self.btn_clear.clicked.connect(self.limpiar)
        
        h_btns.addWidget(self.btn_add)
        h_btns.addWidget(self.btn_update)
        h_btns.addWidget(self.btn_delete)
        h_btns.addWidget(self.btn_clear)
        vbox.addLayout(h_btns)

        # Tabla Visual
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(2)
        self.tabla.setHorizontalHeaderLabels(["ID", "Nombre"])
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.hideColumn(0) 
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla.itemClicked.connect(self.seleccionar)
        
        vbox.addWidget(self.tabla)
        self.group.setLayout(vbox)
        layout.addWidget(self.group)
        self.setLayout(layout)
        self.cargar_datos()

    def cargar_datos(self):
        self.tabla.setRowCount(0)
        datos = self.db.traer_datos(f"SELECT id, nombre FROM {self.tabla_bd}")
        for i, (fid, nom) in enumerate(datos):
            self.tabla.insertRow(i)
            self.tabla.setItem(i, 0, QTableWidgetItem(str(fid)))
            self.tabla.setItem(i, 1, QTableWidgetItem(nom))

    def seleccionar(self):
        row = self.tabla.currentRow()
        if row >= 0:
            self.id_seleccionado = self.tabla.item(row, 0).text()
            self.txt_nombre.setText(self.tabla.item(row, 1).text())
            self.btn_add.setEnabled(False)
            self.btn_update.setEnabled(True)
            self.btn_delete.setEnabled(True)

    def limpiar(self):
        self.txt_nombre.clear()
        self.id_seleccionado = None
        self.tabla.clearSelection()
        self.btn_add.setEnabled(True)
        self.btn_update.setEnabled(False)
        self.btn_delete.setEnabled(False)
    
    def notificar(self):
        if self.callback_cambios: self.callback_cambios()

    def agregar(self):
        if self.txt_nombre.text():
            self.db.ejecutar(f"INSERT INTO {self.tabla_bd} (nombre) VALUES (?)", (self.txt_nombre.text(),))
            self.limpiar()
            self.cargar_datos()
            self.notificar()

    def actualizar(self):
        if self.id_seleccionado and self.txt_nombre.text():
            self.db.ejecutar(f"UPDATE {self.tabla_bd} SET nombre=? WHERE id=?", (self.txt_nombre.text(), self.id_seleccionado))
            self.limpiar()
            self.cargar_datos()
            self.notificar()

    def eliminar(self):
        if self.id_seleccionado:
            if QMessageBox.question(self, "Borrar", "¿Seguro?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
                self.db.ejecutar(f"DELETE FROM {self.tabla_bd} WHERE id=?", (self.id_seleccionado,))
                self.limpiar()
                self.cargar_datos()
                self.notificar()

class ABMSubcategorias(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.id_seleccionado = None
        
        layout = QVBoxLayout()
        self.group = QGroupBox("Gestión de Subcategorías")
        vbox = QVBoxLayout()

        # Formulario
        form = QFormLayout()
        self.txt_nombre = QLineEdit()
        self.cmb_categoria = QComboBox()
        
        form.addRow("Nombre Subcategoría:", self.txt_nombre)
        form.addRow("Pertenece a Categoría:", self.cmb_categoria)
        vbox.addLayout(form)

        # Botones
        h_btns = QHBoxLayout()
        self.btn_add = QPushButton("Agregar")
        self.btn_add.clicked.connect(self.agregar)
        self.btn_update = QPushButton("Actualizar")
        self.btn_update.clicked.connect(self.actualizar)
        self.btn_update.setEnabled(False)
        self.btn_delete = QPushButton("Eliminar")
        self.btn_delete.setStyleSheet("background-color: #dc3545;")
        self.btn_delete.clicked.connect(self.eliminar)
        self.btn_delete.setEnabled(False)
        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.setStyleSheet("background-color: #6c757d;")
        self.btn_clear.clicked.connect(self.limpiar)
        
        h_btns.addWidget(self.btn_add)
        h_btns.addWidget(self.btn_update)
        h_btns.addWidget(self.btn_delete)
        h_btns.addWidget(self.btn_clear)
        vbox.addLayout(h_btns)

        # Tabla
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(4) # ID, Nombre, NombreCat, IDCat
        self.tabla.setHorizontalHeaderLabels(["ID", "Subcategoría", "Categoría", "id_cat"])
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.hideColumn(0) 
        self.tabla.hideColumn(3)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla.itemClicked.connect(self.seleccionar)
        
        vbox.addWidget(self.tabla)
        self.group.setLayout(vbox)
        layout.addWidget(self.group)
        self.setLayout(layout)
        
        self.cargar_categorias()
        self.cargar_datos()

    def cargar_categorias(self):
        id_actual = self.cmb_categoria.currentData()
        self.cmb_categoria.clear()
        cats = self.db.traer_datos("SELECT id, nombre FROM categorias")
        for c in cats:
            self.cmb_categoria.addItem(c[1], c[0])
        if id_actual:
            idx = self.cmb_categoria.findData(id_actual)
            if idx >= 0: self.cmb_categoria.setCurrentIndex(idx)

    def cargar_datos(self):
        self.tabla.setRowCount(0)
        query = '''SELECT s.id, s.nombre, c.nombre, c.id 
                   FROM subcategorias s 
                   LEFT JOIN categorias c ON s.categoria_id = c.id'''
        datos = self.db.traer_datos(query)
        for i, row in enumerate(datos):
            self.tabla.insertRow(i)
            self.tabla.setItem(i, 0, QTableWidgetItem(str(row[0])))
            self.tabla.setItem(i, 1, QTableWidgetItem(row[1]))
            self.tabla.setItem(i, 2, QTableWidgetItem(row[2] if row[2] else "Sin Cat"))
            self.tabla.setItem(i, 3, QTableWidgetItem(str(row[3]) if row[3] else ""))

    def seleccionar(self):
        row = self.tabla.currentRow()
        if row >= 0:
            self.id_seleccionado = self.tabla.item(row, 0).text()
            self.txt_nombre.setText(self.tabla.item(row, 1).text())
            id_cat = self.tabla.item(row, 3).text()
            if id_cat:
                index = self.cmb_categoria.findData(int(id_cat))
                self.cmb_categoria.setCurrentIndex(index)
            self.btn_add.setEnabled(False)
            self.btn_update.setEnabled(True)
            self.btn_delete.setEnabled(True)

    def limpiar(self):
        self.txt_nombre.clear()
        self.id_seleccionado = None
        self.tabla.clearSelection()
        self.btn_add.setEnabled(True)
        self.btn_update.setEnabled(False)
        self.btn_delete.setEnabled(False)

    def agregar(self):
        cat_id = self.cmb_categoria.currentData()
        if self.txt_nombre.text() and cat_id:
            self.db.ejecutar("INSERT INTO subcategorias (nombre, categoria_id) VALUES (?,?)", 
                             (self.txt_nombre.text(), cat_id))
            self.limpiar()
            self.cargar_datos()

    def actualizar(self):
        cat_id = self.cmb_categoria.currentData()
        if self.id_seleccionado and self.txt_nombre.text() and cat_id:
            self.db.ejecutar("UPDATE subcategorias SET nombre=?, categoria_id=? WHERE id=?", 
                             (self.txt_nombre.text(), cat_id, self.id_seleccionado))
            self.limpiar()
            self.cargar_datos()

    def eliminar(self):
        if self.id_seleccionado:
            if QMessageBox.question(self, "Borrar", "¿Seguro?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
                self.db.ejecutar("DELETE FROM subcategorias WHERE id=?", (self.id_seleccionado,))
                self.limpiar()
                self.cargar_datos()

# Interfaz grafica Principal
class SistemaCafeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DataBase()
        self.setWindowTitle("Sistema Café ERP")
        self.setGeometry(50, 50, 1300, 850)
        self.insumo_id_editar = None
        self.producto_seleccionado_id = None
        
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        self.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #AAA; }
            QTabBar::tab { background: #EEE; padding: 10px 20px; border-radius: 4px; margin: 1px; }
            QTabBar::tab:selected { background: #007BFF; color: white; font-weight: bold; }
            QLabel { font-size: 14px; } 
            QLineEdit, QComboBox, QTableWidget { font-size: 14px; } 
            QPushButton { background-color: #28a745; color: white; padding: 6px; border-radius: 4px; font-weight: bold; }
            QPushButton:disabled { background-color: #CCC; }
        """)

        self.init_tab_insumos()
        self.init_tab_config()
        self.init_tab_productos()
        self.init_tab_visor()

    # Pestaña de insumos
    def init_tab_insumos(self):
        tab = QWidget()
        layout = QHBoxLayout()
        
        # Panel formulario
        form_panel = QGroupBox("Gestión de Insumos")
        form_layout = QVBoxLayout()
        
        # Inputs
        self.ins_nombre = QLineEdit()
        self.ins_costo = QLineEdit()
        self.ins_cant_envase = QLineEdit()

        # Combos de unidades
        self.cmb_uni_compra = QComboBox()
        self.cmb_uni_uso = QComboBox()
        
        # Conectar cambios
        self.cmb_uni_compra.currentIndexChanged.connect(self.verificar_conversion)
        self.cmb_uni_uso.currentIndexChanged.connect(self.verificar_conversion)

        # Input conversion
        self.lbl_factor = QLabel("Conversión:")
        self.ins_factor = QLineEdit()
        self.container_factor = QWidget()
        lay_factor = QHBoxLayout()
        lay_factor.addWidget(self.lbl_factor)
        lay_factor.addWidget(self.ins_factor)
        self.container_factor.setLayout(lay_factor)
        self.container_factor.setVisible(False)

        # Botones CRUD
        self.btn_guardar = QPushButton("Guardar Insumo")
        self.btn_guardar.clicked.connect(self.guardar_insumo)

        self.btn_cancelar = QPushButton("Cancelar / Limpiar")
        self.btn_cancelar.setStyleSheet("background-color: #6c757d;")
        self.btn_cancelar.clicked.connect(self.limpiar_formulario_insumos)

        # Layout de botones de acción
        lay_btns = QHBoxLayout()
        lay_btns.addWidget(self.btn_guardar)
        lay_btns.addWidget(self.btn_cancelar)

        # Layout del form
        fl = QFormLayout()
        fl.addRow("Nombre Insumo:", self.ins_nombre)
        fl.addRow("Costo de Compra ($):", self.ins_costo)
        fl.addRow("Unidad de Envase (Compra):", self.cmb_uni_compra)
        fl.addRow("Cantidad en el Envase:", self.ins_cant_envase)
        fl.addRow("Unidad para Recetas (Uso):", self.cmb_uni_uso)
        
        form_layout.addLayout(fl)
        form_layout.addWidget(self.container_factor)
        form_layout.addLayout(lay_btns)
        form_layout.addStretch()
        form_panel.setLayout(form_layout)

        right_layout = QVBoxLayout()
        self.tabla_insumos = QTableWidget()
        cols = ["ID", "Insumo", "Envase", "Costo", "Conv.", "Rendimiento", "Costo Unitario"]
        self.tabla_insumos.setColumnCount(len(cols))
        self.tabla_insumos.setHorizontalHeaderLabels(cols)
        self.tabla_insumos.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabla_insumos.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla_insumos.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla_insumos.setSelectionMode(QAbstractItemView.SingleSelection)

        # Botones para Editar/Eliminar
        hbox_crud = QHBoxLayout()
        btn_editar = QPushButton("Editar Seleccionado")
        btn_editar.setStyleSheet("background-color: #ffc107; color: black;")
        btn_editar.clicked.connect(self.cargar_para_editar)
        
        btn_eliminar = QPushButton("Eliminar Seleccionado")
        btn_eliminar.setStyleSheet("background-color: #dc3545;")
        btn_eliminar.clicked.connect(self.eliminar_insumo)
        
        hbox_crud.addWidget(btn_editar)
        hbox_crud.addWidget(btn_eliminar)

        right_layout.addWidget(self.tabla_insumos)
        right_layout.addLayout(hbox_crud)

        layout.addWidget(form_panel, 1)
        layout.addLayout(right_layout, 2)
        tab.setLayout(layout)
        self.tabs.addTab(tab, "INSUMOS")
        
        self.cargar_unidades_combo()
        self.cargar_tabla_insumos()

    def cargar_unidades_combo(self):
        id_compra_prev = self.cmb_uni_compra.currentData()
        id_uso_prev = self.cmb_uni_uso.currentData()
        self.cmb_uni_compra.clear()
        self.cmb_uni_uso.clear()
        unis = self.db.traer_datos("SELECT id, nombre FROM unidades")
        for u in unis:
            self.cmb_uni_compra.addItem(u[1], u[0])
            self.cmb_uni_uso.addItem(u[1], u[0])
        if id_compra_prev: 
            idx = self.cmb_uni_compra.findData(id_compra_prev)
            if idx >= 0: self.cmb_uni_compra.setCurrentIndex(idx)
        if id_uso_prev:
            idx = self.cmb_uni_uso.findData(id_uso_prev)
            if idx >= 0: self.cmb_uni_uso.setCurrentIndex(idx)

    def verificar_conversion(self):
        id_compra = self.cmb_uni_compra.currentData()
        id_uso = self.cmb_uni_uso.currentData()
        if id_compra != id_uso and id_compra is not None:
            self.container_factor.setVisible(True)
            txt_compra = self.cmb_uni_compra.currentText()
            txt_uso = self.cmb_uni_uso.currentText()
            self.lbl_factor.setText(f"1 {txt_compra} equivale a cuántos {txt_uso}?:")
        else:
            self.container_factor.setVisible(False)

    def limpiar_formulario_insumos(self):
        self.ins_nombre.clear()
        self.ins_costo.clear()
        self.ins_cant_envase.clear()
        self.ins_factor.clear()
        self.insumo_id_editar = None
        self.btn_guardar.setText("Guardar Insumo")
        self.btn_guardar.setStyleSheet("background-color: #28a745; color: white;")
        self.tabla_insumos.clearSelection()

    def cargar_para_editar(self):
        rows = self.tabla_insumos.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        id_insumo = self.tabla_insumos.item(row, 0).text() 
        data = self.db.traer_datos("SELECT * FROM insumos WHERE id=?", (id_insumo,))
        if not data: return
        reg = data[0]
        self.insumo_id_editar = reg[0]
        self.ins_nombre.setText(reg[1])
        idx_compra = self.cmb_uni_compra.findData(reg[2])
        if idx_compra >= 0: self.cmb_uni_compra.setCurrentIndex(idx_compra)
        idx_uso = self.cmb_uni_uso.findData(reg[3])
        if idx_uso >= 0: self.cmb_uni_uso.setCurrentIndex(idx_uso)
        self.ins_cant_envase.setText(str(reg[4]))
        self.ins_costo.setText(str(reg[5]))
        self.ins_factor.setText(str(reg[6]))
        self.btn_guardar.setText("Actualizar Insumo")
        self.btn_guardar.setStyleSheet("background-color: #007bff; color: white;")

    def eliminar_insumo(self):
        rows = self.tabla_insumos.selectionModel().selectedRows()
        if not rows: return
        row = rows[0].row()
        id_insumo = self.tabla_insumos.item(row, 0).text()
        if QMessageBox.question(self, "Confirmar", "¿Eliminar insumo?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            if self.db.ejecutar("DELETE FROM insumos WHERE id=?", (id_insumo,)):
                self.cargar_tabla_insumos()
                self.limpiar_formulario_insumos()

    def guardar_insumo(self):
        try:
            nombre = self.ins_nombre.text()
            if not nombre: return
            costo_envase = float(self.ins_costo.text())
            cant_envase = float(self.ins_cant_envase.text())
            id_compra = self.cmb_uni_compra.currentData()
            id_uso = self.cmb_uni_uso.currentData()
            factor = 1.0
            if id_compra != id_uso:
                factor = float(self.ins_factor.text())
            rendimiento_bruto = cant_envase * factor
            rendimiento_real = math.floor(rendimiento_bruto)
            if rendimiento_real == 0:
                QMessageBox.warning(self, "Error", "El rendimiento da 0.")
                return
            costo_unitario = costo_envase / rendimiento_real
            if self.insumo_id_editar is None:
                self.db.ejecutar('''INSERT INTO insumos (nombre, unidad_compra_id, unidad_uso_id, cantidad_envase, costo_envase, factor_conversion, rendimiento_total, costo_unitario) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (nombre, id_compra, id_uso, cant_envase, costo_envase, factor, rendimiento_real, costo_unitario))
                msg = "Creado"
            else:
                self.db.ejecutar('''UPDATE insumos SET nombre=?, unidad_compra_id=?, unidad_uso_id=?, cantidad_envase=?, costo_envase=?, factor_conversion=?, rendimiento_total=?, costo_unitario=? WHERE id=?''', (nombre, id_compra, id_uso, cant_envase, costo_envase, factor, rendimiento_real, costo_unitario, self.insumo_id_editar))
                msg = "Actualizado"
            self.limpiar_formulario_insumos()
            self.cargar_tabla_insumos()
            QMessageBox.information(self, "Listo", f"{msg}\nCosto por Uso: ${costo_unitario:.4f}")
        except ValueError:
            QMessageBox.warning(self, "Error", "Revisar los números.")

    def cargar_tabla_insumos(self):
        query = '''SELECT i.id, i.nombre, (i.cantidad_envase || ' ' || u1.nombre), i.costo_envase, i.factor_conversion, (i.rendimiento_total || ' ' || u2.nombre), i.costo_unitario FROM insumos i JOIN unidades u1 ON i.unidad_compra_id = u1.id JOIN unidades u2 ON i.unidad_uso_id = u2.id ORDER BY i.id DESC'''
        datos = self.db.traer_datos(query)
        self.tabla_insumos.setSortingEnabled(False)
        self.tabla_insumos.setRowCount(0)
        for row_idx, row_data in enumerate(datos):
            self.tabla_insumos.insertRow(row_idx)
            for col_idx, col_data in enumerate(row_data):
                val = str(col_data)
                if col_idx == 6: val = f"${col_data:.4f}"
                if col_idx == 3: val = f"${col_data:.2f}"
                if col_idx in [0, 3, 4, 6]: self.tabla_insumos.setItem(row_idx, col_idx, NumericTableWidgetItem(val))
                else: self.tabla_insumos.setItem(row_idx, col_idx, QTableWidgetItem(val))
        self.tabla_insumos.setSortingEnabled(True)

    # --- PESTAÑA CONFIGURACIÓN ---
    def init_tab_config(self):
        tab = QWidget()
        layout = QGridLayout()
        self.abm_subcategorias = ABMSubcategorias(self.db)
        def actualizar_dependencias_categorias():
            self.abm_subcategorias.cargar_categorias() 
            self.abm_subcategorias.cargar_datos() 
            # También refrescar combos de productos
            self.cargar_cat_prod()
            
        self.abm_categorias = ABMSimple("Categorías", "categorias", self.db, callback_cambios=actualizar_dependencias_categorias)
        self.abm_tamanos = ABMSimple("Tamaños", "tamanos", self.db)
        self.abm_unidades = ABMSimple("Unidades de Medida", "unidades", self.db)
        layout.addWidget(self.abm_categorias, 0, 0)
        layout.addWidget(self.abm_subcategorias, 0, 1)
        layout.addWidget(self.abm_tamanos, 1, 0)
        layout.addWidget(self.abm_unidades, 1, 1)
        tab.setLayout(layout)
        self.tabs.addTab(tab, "CONFIGURACIÓN")

    # --- PESTAÑA PRODUCTOS Y RECETAS (CRUD ACTUALIZADO) ---
    def init_tab_productos(self):
        tab = QWidget()
        layout = QHBoxLayout()

        # COLUMNA 1: LISTADO DE PRODUCTOS (READ)
        col1 = QGroupBox("1. Seleccionar Producto")
        l1 = QVBoxLayout()
        self.lista_productos = QTableWidget()
        self.lista_productos.setColumnCount(2)
        self.lista_productos.setHorizontalHeaderLabels(["ID", "Nombre"])
        self.lista_productos.hideColumn(0)
        self.lista_productos.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.lista_productos.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.lista_productos.setSelectionMode(QAbstractItemView.SingleSelection)
        self.lista_productos.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.lista_productos.itemClicked.connect(self.seleccionar_producto_crud)
        l1.addWidget(self.lista_productos)
        
        btn_nuevo_prod = QPushButton("Nuevo Producto")
        btn_nuevo_prod.clicked.connect(self.limpiar_form_producto)
        l1.addWidget(btn_nuevo_prod)
        col1.setLayout(l1)

        # COLUMNA 2: DETALLES DEL PRODUCTO (CREATE/UPDATE/DELETE)
        col2 = QGroupBox("2. Definir Producto")
        l2 = QVBoxLayout()
        form_prod = QFormLayout()
        self.prod_nombre = QLineEdit()
        self.prod_cat = QComboBox()
        self.prod_subcat = QComboBox()
        self.prod_cat.currentIndexChanged.connect(self.filtrar_subcats_prod)

        form_prod.addRow("Nombre:", self.prod_nombre)
        form_prod.addRow("Categoría:", self.prod_cat)
        form_prod.addRow("Subcategoría:", self.prod_subcat)
        l2.addLayout(form_prod)

        l2.addWidget(QLabel("<b>Pasos de la Receta:</b>"))
        self.lista_pasos = QListWidget()
        l2.addWidget(self.lista_pasos)
        
        h_paso = QHBoxLayout()
        self.txt_paso = QLineEdit()
        self.txt_paso.setPlaceholderText("Describir paso...")
        self.txt_paso.returnPressed.connect(self.agregar_paso) # Enter para agregar
        btn_add_paso = QPushButton("+")
        btn_add_paso.setFixedWidth(40)
        btn_add_paso.clicked.connect(self.agregar_paso)
        btn_del_paso = QPushButton("-")
        btn_del_paso.setFixedWidth(40)
        btn_del_paso.clicked.connect(self.borrar_paso)
        h_paso.addWidget(self.txt_paso)
        h_paso.addWidget(btn_add_paso)
        h_paso.addWidget(btn_del_paso)
        l2.addLayout(h_paso)

        h_btns_prod = QHBoxLayout()
        self.btn_guardar_prod = QPushButton("Guardar Producto")
        self.btn_guardar_prod.clicked.connect(self.guardar_producto)
        self.btn_borrar_prod = QPushButton("Eliminar Producto")
        self.btn_borrar_prod.setStyleSheet("background-color: #dc3545;")
        self.btn_borrar_prod.clicked.connect(self.eliminar_producto)
        h_btns_prod.addWidget(self.btn_guardar_prod)
        h_btns_prod.addWidget(self.btn_borrar_prod)
        l2.addLayout(h_btns_prod)
        col2.setLayout(l2)

        # COLUMNA 3: INGREDIENTES POR TAMAÑO
        col3 = QGroupBox("3. Ingredientes por Tamaño")
        l3 = QVBoxLayout()
        
        self.lbl_prod_sel = QLabel("Ningún producto seleccionado")
        self.lbl_prod_sel.setStyleSheet("color: gray; font-style: italic;")
        l3.addWidget(self.lbl_prod_sel)

        h_tam = QHBoxLayout()
        self.sel_tamano = QComboBox()
        btn_hab_tam = QPushButton("Asignar/Ver Tamaño")
        btn_hab_tam.clicked.connect(self.cargar_tabla_receta) # Al asignar, cargamos
        h_tam.addWidget(self.sel_tamano)
        h_tam.addWidget(btn_hab_tam)
        l3.addLayout(h_tam)

        l3.addWidget(QLabel("Agregar Insumo:"))
        h_ing = QHBoxLayout()
        self.sel_insumo_receta = QComboBox()
        self.txt_cant_receta = QLineEdit()
        self.txt_cant_receta.setPlaceholderText("Cant.")
        self.lbl_unidad_insumo = QLabel("u.")
        btn_add_ing = QPushButton("+")
        btn_add_ing.clicked.connect(self.agregar_ingrediente)
        
        h_ing.addWidget(self.sel_insumo_receta, 2)
        h_ing.addWidget(self.txt_cant_receta, 1)
        h_ing.addWidget(self.lbl_unidad_insumo)
        h_ing.addWidget(btn_add_ing)
        l3.addLayout(h_ing)
        self.sel_insumo_receta.currentIndexChanged.connect(self.actualizar_lbl_unidad)

        self.tabla_receta = QTableWidget()
        self.tabla_receta.setColumnCount(4) # ID, Insumo, Cant, Costo
        self.tabla_receta.setHorizontalHeaderLabels(["ID", "Insumo", "Cantidad", "Costo"])
        self.tabla_receta.hideColumn(0)
        self.tabla_receta.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        l3.addWidget(self.tabla_receta)
        
        btn_del_ing = QPushButton("Quitar Insumo Seleccionado")
        btn_del_ing.setStyleSheet("background-color: #ffc107; color: black;")
        btn_del_ing.clicked.connect(self.borrar_ingrediente)
        l3.addWidget(btn_del_ing)
        
        col3.setLayout(l3)
        
        # Configurar visibilidad inicial
        col3.setEnabled(False) # Se habilita al seleccionar producto
        self.panel_ingredientes = col3

        layout.addWidget(col1, 1)
        layout.addWidget(col2, 2)
        layout.addWidget(col3, 2)
        tab.setLayout(layout)
        self.tabs.addTab(tab, "RECETAS")

        self.tabs.currentChanged.connect(self.al_cambiar_tab)
        self.sel_tamano.currentIndexChanged.connect(self.cargar_tabla_receta)

    def al_cambiar_tab(self, index):
        if index == 0: 
            self.cargar_unidades_combo()
            self.cargar_tabla_insumos()
        if index == 1: 
            self.abm_categorias.cargar_datos()
            self.abm_tamanos.cargar_datos()
            self.abm_unidades.cargar_datos()
            self.abm_subcategorias.cargar_categorias()
            self.abm_subcategorias.cargar_datos()
        if index == 2: 
            self.cargar_lista_productos()
            self.cargar_cat_prod()
            self.cargar_combos_ingredientes()
        if index == 3: 
            self.recargar_visor()

    # --- LÓGICA DE PRODUCTOS ---
    def cargar_cat_prod(self):
        self.prod_cat.clear()
        self.prod_cat.addItem("- Sin Categoría -", None)
        for c in self.db.traer_datos("SELECT id, nombre FROM categorias"):
            self.prod_cat.addItem(c[1], c[0])
        
    def filtrar_subcats_prod(self):
        self.prod_subcat.clear()
        self.prod_subcat.addItem("- Sin Subcategoría -", None)
        cat_id = self.prod_cat.currentData()
        if cat_id:
            query = "SELECT id, nombre FROM subcategorias WHERE categoria_id=?"
            for s in self.db.traer_datos(query, (cat_id,)):
                self.prod_subcat.addItem(s[1], s[0])

    def cargar_lista_productos(self):
        self.lista_productos.setRowCount(0)
        for row, (pid, nom) in enumerate(self.db.traer_datos("SELECT id, nombre FROM productos ORDER BY nombre")):
            self.lista_productos.insertRow(row)
            self.lista_productos.setItem(row, 0, QTableWidgetItem(str(pid)))
            self.lista_productos.setItem(row, 1, QTableWidgetItem(nom))

    def limpiar_form_producto(self):
        self.producto_seleccionado_id = None
        self.prod_nombre.clear()
        self.prod_cat.setCurrentIndex(0)
        self.prod_subcat.setCurrentIndex(0)
        self.lista_pasos.clear()
        self.lista_productos.clearSelection()
        self.panel_ingredientes.setEnabled(False)
        self.lbl_prod_sel.setText("Nuevo Producto (Sin guardar)")
        self.btn_guardar_prod.setText("Crear Producto")
        self.btn_borrar_prod.setEnabled(False)

    def seleccionar_producto_crud(self):
        row = self.lista_productos.currentRow()
        if row < 0: return
        pid = int(self.lista_productos.item(row, 0).text())
        self.producto_seleccionado_id = pid
        
        # Cargar Datos Básicos
        data = self.db.traer_datos("SELECT nombre, categoria_id, subcategoria_id FROM productos WHERE id=?", (pid,))[0]
        self.prod_nombre.setText(data[0])
        
        idx_cat = self.prod_cat.findData(data[1])
        if idx_cat >= 0: self.prod_cat.setCurrentIndex(idx_cat)
        
        # Esperar a que se actualice el combo subcat
        idx_sub = self.prod_subcat.findData(data[2])
        if idx_sub >= 0: self.prod_subcat.setCurrentIndex(idx_sub)

        # Cargar Pasos
        self.lista_pasos.clear()
        pasos = self.db.traer_datos("SELECT descripcion FROM receta_pasos WHERE producto_id=? ORDER BY orden", (pid,))
        for p in pasos:
            self.lista_pasos.addItem(p[0])

        # Habilitar panel derecho
        self.panel_ingredientes.setEnabled(True)
        self.lbl_prod_sel.setText(f"Editando: {data[0]}")
        self.btn_guardar_prod.setText("Actualizar Producto")
        self.btn_borrar_prod.setEnabled(True)
        self.cargar_tabla_receta() # Carga receta del tamaño seleccionado

    def agregar_paso(self):
        txt = self.txt_paso.text()
        if txt:
            self.lista_pasos.addItem(txt)
            self.txt_paso.clear()

    def borrar_paso(self):
        row = self.lista_pasos.currentRow()
        if row >= 0:
            self.lista_pasos.takeItem(row)

    def guardar_producto(self):
        nombre = self.prod_nombre.text()
        if not nombre:
            QMessageBox.warning(self, "Error", "Falta el nombre")
            return
        
        cat_id = self.prod_cat.currentData()
        subcat_id = self.prod_subcat.currentData()
        
        # Guardar Encabezado
        if self.producto_seleccionado_id is None:
            self.db.ejecutar("INSERT INTO productos (nombre, categoria_id, subcategoria_id) VALUES (?,?,?)", 
                             (nombre, cat_id, subcat_id))
            # Obtener ID del nuevo
            self.producto_seleccionado_id = self.db.cursor.lastrowid
            msg = "Producto Creado"
        else:
            self.db.ejecutar("UPDATE productos SET nombre=?, categoria_id=?, subcategoria_id=? WHERE id=?", 
                             (nombre, cat_id, subcat_id, self.producto_seleccionado_id))
            msg = "Producto Actualizado"

        # Guardar Pasos (Borrar anteriores e insertar nuevos)
        self.db.ejecutar("DELETE FROM receta_pasos WHERE producto_id=?", (self.producto_seleccionado_id,))
        for i in range(self.lista_pasos.count()):
            paso_texto = self.lista_pasos.item(i).text()
            self.db.ejecutar("INSERT INTO receta_pasos (producto_id, orden, descripcion) VALUES (?,?,?)",
                             (self.producto_seleccionado_id, i+1, paso_texto))
        
        self.cargar_lista_productos()
        self.panel_ingredientes.setEnabled(True)
        self.lbl_prod_sel.setText(f"Editando: {nombre}")
        self.btn_guardar_prod.setText("Actualizar Producto")
        self.btn_borrar_prod.setEnabled(True)
        QMessageBox.information(self, "Éxito", msg)

    def eliminar_producto(self):
        if not self.producto_seleccionado_id: return
        if QMessageBox.question(self, "Eliminar", "Esto borrará el producto y sus recetas. ¿Seguro?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            # Foreign keys con CASCADE deberían encargarse, pero por seguridad:
            pid = self.producto_seleccionado_id
            self.db.ejecutar("DELETE FROM receta_pasos WHERE producto_id=?", (pid,))
            # Borrar ingredientes de las recetas de este producto
            configs = self.db.traer_datos("SELECT id FROM receta_config WHERE producto_id=?", (pid,))
            for c in configs:
                self.db.ejecutar("DELETE FROM receta_ingredientes WHERE receta_config_id=?", (c[0],))
            self.db.ejecutar("DELETE FROM receta_config WHERE producto_id=?", (pid,))
            self.db.ejecutar("DELETE FROM productos WHERE id=?", (pid,))
            
            self.limpiar_form_producto()
            self.cargar_lista_productos()

    # --- LÓGICA INGREDIENTES ---
    def cargar_combos_ingredientes(self):
        self.sel_tamano.clear()
        for t in self.db.traer_datos("SELECT id, nombre FROM tamanos"):
            self.sel_tamano.addItem(t[1], t[0])

        self.sel_insumo_receta.clear()
        query = "SELECT i.id, i.nombre, u.nombre FROM insumos i JOIN unidades u ON i.unidad_uso_id = u.id"
        for i in self.db.traer_datos(query):
            self.sel_insumo_receta.addItem(f"{i[1]}", {"id": i[0], "unidad": i[2]})
        self.actualizar_lbl_unidad()

    def actualizar_lbl_unidad(self):
        data = self.sel_insumo_receta.currentData()
        if data: self.lbl_unidad_insumo.setText(data["unidad"])

    def habilitar_tamano_config(self):
        # Crea la entrada en receta_config si no existe
        pid = self.producto_seleccionado_id
        tid = self.sel_tamano.currentData()
        if pid and tid:
            self.db.ejecutar("INSERT OR IGNORE INTO receta_config (producto_id, tamano_id) VALUES (?,?)", (pid, tid))
            return True
        return False

    def agregar_ingrediente(self):
        if not self.producto_seleccionado_id: return
        self.habilitar_tamano_config() # Asegurar que existe config
        
        tid = self.sel_tamano.currentData()
        idata = self.sel_insumo_receta.currentData() 
        cant = self.txt_cant_receta.text()

        # Obtener ID config
        rc = self.db.traer_datos("SELECT id FROM receta_config WHERE producto_id=? AND tamano_id=?", (self.producto_seleccionado_id, tid))
        if rc and cant:
            try:
                self.db.ejecutar("INSERT INTO receta_ingredientes (receta_config_id, insumo_id, cantidad_necesaria) VALUES (?,?,?)",
                                 (rc[0][0], idata['id'], float(cant)))
                self.txt_cant_receta.clear()
                self.cargar_tabla_receta()
            except sqlite3.Error as e:
                QMessageBox.warning(self, "Error", f"No se pudo agregar (¿Quizás ya está en la lista?).\n{e}")

    def borrar_ingrediente(self):
        row = self.tabla_receta.currentRow()
        if row < 0: return
        # Necesitamos el insumo_id para borrar, lo tomamos de la tabla?
        # Mejor recargamos la tabla guardando IDs ocultos
        # (Implementación simplificada: borrar por rowid en BD o insumo_id)
        # Aquí usaremos un truco: ID oculto en col 0 es el insumo_id? NO, es mejor traer el rowid de la tabla intermedia.
        # Por simplicidad, asumimos insumo único por receta.
        
        tid = self.sel_tamano.currentData()
        rc = self.db.traer_datos("SELECT id FROM receta_config WHERE producto_id=? AND tamano_id=?", (self.producto_seleccionado_id, tid))
        if not rc: return
        
        # El ID en la columna 0 será el ID del insumo para poder borrarlo
        insumo_id = self.tabla_receta.item(row, 0).text()
        self.db.ejecutar("DELETE FROM receta_ingredientes WHERE receta_config_id=? AND insumo_id=?", (rc[0][0], insumo_id))
        self.cargar_tabla_receta()

    def cargar_tabla_receta(self):
        self.tabla_receta.setRowCount(0)
        pid = self.producto_seleccionado_id
        tid = self.sel_tamano.currentData()
        if not pid or not tid: return

        # Asegurar config para visualizar
        self.db.ejecutar("INSERT OR IGNORE INTO receta_config (producto_id, tamano_id) VALUES (?,?)", (pid, tid))

        query = '''
            SELECT i.id, i.nombre, r.cantidad_necesaria, u.nombre, i.costo_unitario
            FROM receta_ingredientes r
            JOIN insumos i ON r.insumo_id = i.id
            JOIN unidades u ON i.unidad_uso_id = u.id
            JOIN receta_config rc ON r.receta_config_id = rc.id
            WHERE rc.producto_id = ? AND rc.tamano_id = ?
        '''
        datos = self.db.traer_datos(query, (pid, tid))
        total = 0
        for i, row in enumerate(datos):
            self.tabla_receta.insertRow(i)
            costo_parcial = row[2] * row[4]
            total += costo_parcial
            
            self.tabla_receta.setItem(i, 0, QTableWidgetItem(str(row[0]))) # ID Insumo oculto
            self.tabla_receta.setItem(i, 1, QTableWidgetItem(row[1]))
            self.tabla_receta.setItem(i, 2, QTableWidgetItem(f"{row[2]} {row[3]}"))
            self.tabla_receta.setItem(i, 3, QTableWidgetItem(f"${costo_parcial:.2f}"))
        
        rows = self.tabla_receta.rowCount()
        self.tabla_receta.insertRow(rows)
        self.tabla_receta.setItem(rows, 1, QTableWidgetItem("TOTAL COSTO:"))
        self.tabla_receta.setItem(rows, 3, QTableWidgetItem(f"${total:.2f}"))

    # --- PESTAÑA VISOR ---
    def init_tab_visor(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        h = QHBoxLayout()
        self.v_prod = QComboBox()
        self.v_prod.setStyleSheet("font-size: 18px; padding: 5px;")
        self.v_tam = QComboBox()
        self.v_tam.setStyleSheet("font-size: 18px; padding: 5px;")
        h.addWidget(QLabel("Producto:")); h.addWidget(self.v_prod, 1)
        h.addWidget(QLabel("Tamaño:")); h.addWidget(self.v_tam, 1)

        self.v_text = QTextEdit()
        self.v_text.setReadOnly(True)
        self.v_text.setStyleSheet("font-size: 16px; line-height: 1.5;")
        
        layout.addLayout(h)
        layout.addWidget(self.v_text)
        tab.setLayout(layout)
        self.tabs.addTab(tab, "RECETARIO")
        
        self.v_prod.currentIndexChanged.connect(self.cargar_tams_visor)
        self.v_tam.currentIndexChanged.connect(self.mostrar_receta_final)

    def recargar_visor(self):
        self.v_prod.clear()
        for p in self.db.traer_datos("SELECT id, nombre FROM productos ORDER BY nombre"):
            self.v_prod.addItem(p[1], p[0])

    def cargar_tams_visor(self):
        self.v_tam.clear()
        pid = self.v_prod.currentData()
        if not pid: return
        query = "SELECT t.id, t.nombre FROM receta_config rc JOIN tamanos t ON rc.tamano_id = t.id WHERE rc.producto_id=?"
        for t in self.db.traer_datos(query, (pid,)):
            self.v_tam.addItem(t[1], t[0])
        self.mostrar_receta_final()

    def mostrar_receta_final(self):
        pid = self.v_prod.currentData()
        tid = self.v_tam.currentData()
        if not pid: 
            self.v_text.setText("")
            return

        # Info Producto
        p_data = self.db.traer_datos("SELECT nombre, categoria_id, subcategoria_id FROM productos WHERE id=?", (pid,))[0]
        cat_nom = self.db.traer_datos("SELECT nombre FROM categorias WHERE id=?", (p_data[1],))
        cat_str = cat_nom[0][0] if cat_nom else "General"
        
        # Pasos
        pasos = self.db.traer_datos("SELECT orden, descripcion FROM receta_pasos WHERE producto_id=? ORDER BY orden", (pid,))
        
        # Ingredientes (Si hay tamaño seleccionado)
        html_ing = ""
        costo_est = 0
        if tid:
            html_ing = "<h3 style='color:#28a745'>INGREDIENTES:</h3><ul>"
            query = '''
                SELECT i.nombre, r.cantidad_necesaria, u.nombre, i.costo_unitario
                FROM receta_ingredientes r
                JOIN insumos i ON r.insumo_id = i.id
                JOIN unidades u ON i.unidad_uso_id = u.id
                JOIN receta_config rc ON r.receta_config_id = rc.id
                WHERE rc.producto_id = ? AND rc.tamano_id = ?
            '''
            ings = self.db.traer_datos(query, (pid, tid))
            if not ings:
                html_ing += "<li>No hay ingredientes definidos para este tamaño.</li>"
            for ing in ings:
                html_ing += f"<li><b>{ing[0]}:</b> {ing[1]} {ing[2]}</li>"
                costo_est += ing[1] * ing[3]
            html_ing += "</ul>"
            html_ing += f"<p><i>Costo Estimado: ${costo_est:.2f}</i></p>"
        else:
            html_ing = "<p><i>Seleccione un tamaño para ver los ingredientes.</i></p>"

        # Armar HTML
        html = f"<h1 style='color:#007BFF'>{p_data[0]}</h1>"
        html += f"<b>Categoría:</b> {cat_str}<hr>"
        html += html_ing
        html += "<hr><h3 style='color:#17a2b8'>PREPARACIÓN:</h3><ol>"
        if pasos:
            for p in pasos:
                html += f"<li>{p[1]}</li>"
        else:
            html += "<li>Sin instrucciones definidas.</li>"
        html += "</ol>"
        
        self.v_text.setHtml(html)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SistemaCafeApp()
    window.show()
    sys.exit(app.exec_())