import sys
import sqlite3
import math
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTableWidget, QTableWidgetItem, QTabWidget, 
                             QComboBox, QMessageBox, QHeaderView, QSplitter,
                             QFormLayout, QGroupBox, QListWidget, QAbstractItemView, QTextEdit, QDialog)
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
        self.crear_tablas()

    def crear_tablas(self):
        # Tablas de config
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS categorias (id INTEGER PRIMARY KEY, nombre TEXT)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS subcategorias (id INTEGER PRIMARY KEY, nombre TEXT)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS tamanos (id INTEGER PRIMARY KEY, nombre TEXT)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS unidades (id INTEGER PRIMARY KEY, nombre TEXT)''')
        
        # Tabla de insumos
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
            instrucciones TEXT
        )''')

        # Tablas intermedias
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS prod_cat (
            prod_id INTEGER, cat_id INTEGER,
            FOREIGN KEY(prod_id) REFERENCES productos(id),
            FOREIGN KEY(cat_id) REFERENCES categorias(id)
        )''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS prod_subcat (
            prod_id INTEGER, subcat_id INTEGER,
            FOREIGN KEY(prod_id) REFERENCES productos(id),
            FOREIGN KEY(subcat_id) REFERENCES subcategorias(id)
        )''')

        # Config de la receta
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS receta_config (
            id INTEGER PRIMARY KEY,
            producto_id INTEGER,
            tamano_id INTEGER,
            UNIQUE(producto_id, tamano_id),
            FOREIGN KEY(producto_id) REFERENCES productos(id),
            FOREIGN KEY(tamano_id) REFERENCES tamanos(id)
        )''')

        # Ingredientes
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS receta_ingredientes (
            receta_config_id INTEGER,
            insumo_id INTEGER,
            cantidad_necesaria REAL,
            FOREIGN KEY(receta_config_id) REFERENCES receta_config(id),
            FOREIGN KEY(insumo_id) REFERENCES insumos(id)
        )''')
        
        # Datos iniciales
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

# Interfaz grafica
class SistemaCafeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DataBase()
        self.setWindowTitle("Sistema Café ERP 2.0")
        self.setGeometry(50, 50, 1200, 800)
        self.insumo_id_editar = None
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Estilos generales
        self.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #AAA; }
            QTabBar::tab { 
                background: #EEE; 
                padding: 15px 30px; 
                margin: 2px; 
                border-top-left-radius: 8px; 
                border-top-right-radius: 8px;
                font-size: 16px; 
                min-width: 150px;
            }
            QTabBar::tab:selected { background: #007BFF; color: white; font-weight: bold; }
            
            QLabel { font-size: 16px; } 
            QLineEdit, QComboBox { padding: 6px; font-size: 16px; } 
            QGroupBox { font-size: 16px; font-weight: bold; } 
            
            QPushButton { 
                background-color: #28a745; 
                color: white; 
                padding: 10px; 
                border-radius: 5px; 
                font-weight: bold; 
                font-size: 16px; 
            }
            QPushButton:hover { background-color: #218838; }
            
            QTableWidget { font-size: 15px; } 
            QHeaderView::section { font-size: 15px; font-weight: bold; } 
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

        # Panel Tabla + Botones de Tabla
        right_layout = QVBoxLayout()
        
        self.tabla_insumos = QTableWidget()
        cols = ["ID", "Insumo", "Envase", "Costo", "Conv.", "Rendimiento", "Costo Unitario"]
        self.tabla_insumos.setColumnCount(len(cols))
        self.tabla_insumos.setHorizontalHeaderLabels(cols)
        self.tabla_insumos.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Configuración de tabla
        self.tabla_insumos.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla_insumos.setSortingEnabled(True)

        # Selección de fila completa
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
            
        # Restaurar si es posible
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
        self.btn_guardar.setStyleSheet("background-color: #28a745; color: white;") # Verde
        self.tabla_insumos.clearSelection()

    def cargar_para_editar(self):
        rows = self.tabla_insumos.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "Aviso", "Selecciona un insumo de la tabla para editar.")
            return
        
        row = rows[0].row()
        id_insumo = self.tabla_insumos.item(row, 0).text() 
        
        data = self.db.traer_datos("SELECT * FROM insumos WHERE id=?", (id_insumo,))
        if not data:
            return
        
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
        self.btn_guardar.setStyleSheet("background-color: #007bff; color: white;") # Azul

    def eliminar_insumo(self):
        rows = self.tabla_insumos.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "Aviso", "Selecciona un insumo para eliminar.")
            return
            
        row = rows[0].row()
        id_insumo = self.tabla_insumos.item(row, 0).text()
        nombre = self.tabla_insumos.item(row, 1).text()
        
        confirm = QMessageBox.question(self, "Confirmar", 
                                     f"¿Estás seguro de eliminar '{nombre}'?\nEsto podría afectar recetas que lo usen.",
                                     QMessageBox.Yes | QMessageBox.No)
        
        if confirm == QMessageBox.Yes:
            res = self.db.ejecutar("DELETE FROM insumos WHERE id=?", (id_insumo,))
            if res:
                self.cargar_tabla_insumos()
                self.limpiar_formulario_insumos()
                QMessageBox.information(self, "Eliminado", "Insumo eliminado correctamente.")
            else:
                QMessageBox.critical(self, "Error", "No se pudo eliminar. Puede que esté en uso en alguna receta.")

    def guardar_insumo(self):
        try:
            nombre = self.ins_nombre.text()
            if not nombre:
                QMessageBox.warning(self, "Error", "Falta el nombre.")
                return

            costo_envase = float(self.ins_costo.text())
            cant_envase = float(self.ins_cant_envase.text())
            id_compra = self.cmb_uni_compra.currentData()
            id_uso = self.cmb_uni_uso.currentData()
            
            factor = 1.0
            if id_compra != id_uso:
                if not self.ins_factor.text():
                    QMessageBox.warning(self, "Atención", "Falta el factor de conversión.")
                    return
                factor = float(self.ins_factor.text())
            
            rendimiento_bruto = cant_envase * factor
            rendimiento_real = math.floor(rendimiento_bruto)
            
            if rendimiento_real == 0:
                QMessageBox.warning(self, "Error", "El rendimiento da 0.")
                return

            costo_unitario = costo_envase / rendimiento_real

            if self.insumo_id_editar is None:
                # CREATE
                self.db.ejecutar('''INSERT INTO insumos 
                    (nombre, unidad_compra_id, unidad_uso_id, cantidad_envase, costo_envase, factor_conversion, rendimiento_total, costo_unitario)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (nombre, id_compra, id_uso, cant_envase, costo_envase, factor, rendimiento_real, costo_unitario))
                msg = "Insumo creado."
            else:
                # UPDATE
                self.db.ejecutar('''UPDATE insumos SET
                    nombre=?, unidad_compra_id=?, unidad_uso_id=?, cantidad_envase=?, costo_envase=?, 
                    factor_conversion=?, rendimiento_total=?, costo_unitario=?
                    WHERE id=?''',
                    (nombre, id_compra, id_uso, cant_envase, costo_envase, factor, rendimiento_real, costo_unitario, self.insumo_id_editar))
                msg = "Insumo actualizado."

            self.limpiar_formulario_insumos()
            self.cargar_tabla_insumos()
            
            QMessageBox.information(self, "Listo", f"{msg}\nCosto por {self.cmb_uni_uso.currentText()}: ${costo_unitario:.4f}")

        except ValueError:
            QMessageBox.warning(self, "Error", "Revisar los números (costos, cantidades).")

    def cargar_tabla_insumos(self):
        query = '''
            SELECT i.id, i.nombre, 
                   (i.cantidad_envase || ' ' || u1.nombre), 
                   i.costo_envase, 
                   i.factor_conversion, 
                   (i.rendimiento_total || ' ' || u2.nombre), 
                   i.costo_unitario
            FROM insumos i
            JOIN unidades u1 ON i.unidad_compra_id = u1.id
            JOIN unidades u2 ON i.unidad_uso_id = u2.id
            ORDER BY i.id DESC
        '''
        datos = self.db.traer_datos(query)
        self.tabla_insumos.setSortingEnabled(False)
        self.tabla_insumos.setRowCount(0)
        
        for row_idx, row_data in enumerate(datos):
            self.tabla_insumos.insertRow(row_idx)
            for col_idx, col_data in enumerate(row_data):
                val = str(col_data)
                
                # Formato visual para monedas
                if col_idx == 6: val = f"${col_data:.4f}"
                if col_idx == 3: val = f"${col_data:.2f}"
                
                # Usar NumericTableWidgetItem para columnas numéricas: ID(0), Costo(3), Factor(4), Costo Unitario(6)
                if col_idx in [0, 3, 4, 6]:
                    self.tabla_insumos.setItem(row_idx, col_idx, NumericTableWidgetItem(val))
                else:
                    self.tabla_insumos.setItem(row_idx, col_idx, QTableWidgetItem(val))
        
        # Reactivamos sorting
        self.tabla_insumos.setSortingEnabled(True)

    # Pestaña de config
    def init_tab_config(self):
        tab = QWidget()
        layout = QHBoxLayout()
        
        def crear_mini_crud(titulo, tabla, input_field, btn_action, lista_widget):
            group = QGroupBox(titulo)
            vbox = QVBoxLayout()
            h_in = QHBoxLayout()
            h_in.addWidget(input_field)
            h_in.addWidget(btn_action)
            vbox.addLayout(h_in)
            vbox.addWidget(lista_widget)
            group.setLayout(vbox)
            return group

        # Categorias
        self.txt_cat = QLineEdit()
        self.list_cat = QListWidget()
        btn_cat = QPushButton("+")
        btn_cat.clicked.connect(lambda: self.add_simple("categorias", self.txt_cat))
        
        # Subcategorias
        self.txt_sub = QLineEdit()
        self.list_sub = QListWidget()
        btn_sub = QPushButton("+")
        btn_sub.clicked.connect(lambda: self.add_simple("subcategorias", self.txt_sub))

        # Tamanos
        self.txt_tam = QLineEdit()
        self.list_tam = QListWidget()
        btn_tam = QPushButton("+")
        btn_tam.clicked.connect(lambda: self.add_simple("tamanos", self.txt_tam))

        # Unidades
        self.txt_uni = QLineEdit()
        self.list_uni = QListWidget()
        btn_uni = QPushButton("+")
        btn_uni.clicked.connect(lambda: self.add_simple("unidades", self.txt_uni))

        layout.addWidget(crear_mini_crud("Categorías", "categorias", self.txt_cat, btn_cat, self.list_cat))
        layout.addWidget(crear_mini_crud("Subcategorías", "subcategorias", self.txt_sub, btn_sub, self.list_sub))
        layout.addWidget(crear_mini_crud("Tamaños", "tamanos", self.txt_tam, btn_tam, self.list_tam))
        layout.addWidget(crear_mini_crud("Unidades de Medida", "unidades", self.txt_uni, btn_uni, self.list_uni))
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "CONFIGURACIÓN")

    def add_simple(self, tabla, input_obj):
        val = input_obj.text()
        if val:
            self.db.ejecutar(f"INSERT INTO {tabla} (nombre) VALUES (?)", (val,))
            input_obj.clear()
            self.refresh_config_lists()
            if tabla == "unidades": self.cargar_unidades_combo()

    def refresh_config_lists(self):
        for tabla, lista_widget in [("categorias", self.list_cat), ("subcategorias", self.list_sub), 
                                    ("tamanos", self.list_tam), ("unidades", self.list_uni)]:
            lista_widget.clear()
            datos = self.db.traer_datos(f"SELECT nombre FROM {tabla}")
            for d in datos: lista_widget.addItem(d[0])

    # Pestaña productos
    def init_tab_productos(self):
        tab = QWidget()
        layout = QHBoxLayout()

        # Panel izq
        left_panel = QGroupBox("1. Definir Producto")
        l_layout = QVBoxLayout()
        self.prod_nombre = QLineEdit()
        self.prod_nombre.setPlaceholderText("Nombre del Producto")
        self.prod_instrucciones = QTextEdit()
        self.prod_instrucciones.setPlaceholderText("Instrucciones generales...")
        
        btn_crear = QPushButton("Crear Producto")
        btn_crear.clicked.connect(self.crear_producto)
        
        l_layout.addWidget(QLabel("Nombre:"))
        l_layout.addWidget(self.prod_nombre)
        l_layout.addWidget(QLabel("Pasos:"))
        l_layout.addWidget(self.prod_instrucciones)
        l_layout.addWidget(btn_crear)
        l_layout.addStretch()
        left_panel.setLayout(l_layout)

        # Panel der
        right_panel = QGroupBox("2. Configurar Ingredientes por Tamaño")
        r_layout = QVBoxLayout()
        
        h_sel = QHBoxLayout()
        self.sel_producto = QComboBox()
        self.sel_tamano = QComboBox()
        btn_hab = QPushButton("Asignar Tamaño")
        btn_hab.setStyleSheet("background-color: #17a2b8; font-size: 16px;") 
        btn_hab.clicked.connect(self.habilitar_tamano)
        
        h_sel.addWidget(self.sel_producto, 2)
        h_sel.addWidget(self.sel_tamano, 1)
        h_sel.addWidget(btn_hab)

        h_ing = QHBoxLayout()
        self.sel_insumo_receta = QComboBox()
        self.txt_cant_receta = QLineEdit()
        self.txt_cant_receta.setPlaceholderText("Cantidad")
        self.lbl_unidad_insumo = QLabel("u.")
        btn_add_ing = QPushButton("Agregar")
        btn_add_ing.clicked.connect(self.agregar_ingrediente)
        
        h_ing.addWidget(self.sel_insumo_receta, 2)
        h_ing.addWidget(self.txt_cant_receta, 1)
        h_ing.addWidget(self.lbl_unidad_insumo)
        h_ing.addWidget(btn_add_ing)

        # Al cambiar insumo
        self.sel_insumo_receta.currentIndexChanged.connect(self.actualizar_lbl_unidad)

        self.tabla_receta = QTableWidget()
        self.tabla_receta.setColumnCount(3)
        self.tabla_receta.setHorizontalHeaderLabels(["Insumo", "Cantidad", "Costo Parcial"])
        self.tabla_receta.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        r_layout.addLayout(h_sel)
        r_layout.addWidget(QLabel("--- Agregar Ingredientes ---"))
        r_layout.addLayout(h_ing)
        r_layout.addWidget(self.tabla_receta)
        right_panel.setLayout(r_layout)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        layout.addWidget(splitter)
        tab.setLayout(layout)
        self.tabs.addTab(tab, "RECETAS")

        self.tabs.currentChanged.connect(self.al_cambiar_tab)
        self.sel_producto.currentIndexChanged.connect(self.cargar_tabla_receta)
        self.sel_tamano.currentIndexChanged.connect(self.cargar_tabla_receta)

    def al_cambiar_tab(self, index):
        if index == 0: self.cargar_unidades_combo(); self.cargar_tabla_insumos()
        if index == 1: self.refresh_config_lists()
        if index == 2: self.recargar_combos_receta()
        if index == 3: self.recargar_visor()

    def recargar_combos_receta(self):
        self.sel_producto.clear()
        for p in self.db.traer_datos("SELECT id, nombre FROM productos"):
            self.sel_producto.addItem(p[1], p[0])
        
        self.sel_tamano.clear()
        for t in self.db.traer_datos("SELECT id, nombre FROM tamanos"):
            self.sel_tamano.addItem(t[1], t[0])

        self.sel_insumo_receta.clear()
        # Traer datos
        query = "SELECT i.id, i.nombre, u.nombre FROM insumos i JOIN unidades u ON i.unidad_uso_id = u.id"
        for i in self.db.traer_datos(query):
            self.sel_insumo_receta.addItem(f"{i[1]}", {"id": i[0], "unidad": i[2]})
        self.actualizar_lbl_unidad()

    def actualizar_lbl_unidad(self):
        data = self.sel_insumo_receta.currentData()
        if data:
            self.lbl_unidad_insumo.setText(data["unidad"])

    def crear_producto(self):
        if self.prod_nombre.text():
            self.db.ejecutar("INSERT INTO productos (nombre, instrucciones) VALUES (?,?)", 
                             (self.prod_nombre.text(), self.prod_instrucciones.toPlainText()))
            self.prod_nombre.clear()
            self.prod_instrucciones.clear()
            self.recargar_combos_receta()
            QMessageBox.information(self, "Ok", "Producto creado.")

    def habilitar_tamano(self):
        pid = self.sel_producto.currentData()
        tid = self.sel_tamano.currentData()
        self.db.ejecutar("INSERT OR IGNORE INTO receta_config (producto_id, tamano_id) VALUES (?,?)", (pid, tid))
        self.cargar_tabla_receta()

    def agregar_ingrediente(self):
        pid = self.sel_producto.currentData()
        tid = self.sel_tamano.currentData()
        idata = self.sel_insumo_receta.currentData() 
        cant = self.txt_cant_receta.text()

        receta_conf = self.db.traer_datos("SELECT id FROM receta_config WHERE producto_id=? AND tamano_id=?", (pid, tid))
        if receta_conf and cant:
            try:
                self.db.ejecutar("INSERT INTO receta_ingredientes (receta_config_id, insumo_id, cantidad_necesaria) VALUES (?,?,?)",
                                 (receta_conf[0][0], idata['id'], float(cant)))
                self.txt_cant_receta.clear()
                self.cargar_tabla_receta()
            except:
                QMessageBox.warning(self, "Error", "Error al agregar.")

    def cargar_tabla_receta(self):
        self.tabla_receta.setRowCount(0)
        pid = self.sel_producto.currentData()
        tid = self.sel_tamano.currentData()
        if not pid or not tid: return

        query = '''
            SELECT i.nombre, r.cantidad_necesaria, u.nombre, i.costo_unitario
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
            costo_parcial = row[1] * row[3]
            total += costo_parcial
            
            self.tabla_receta.setItem(i, 0, QTableWidgetItem(row[0]))
            self.tabla_receta.setItem(i, 1, QTableWidgetItem(f"{row[1]} {row[2]}"))
            self.tabla_receta.setItem(i, 2, QTableWidgetItem(f"${costo_parcial:.2f}"))
        
        # Fila Total
        rows = self.tabla_receta.rowCount()
        self.tabla_receta.insertRow(rows)
        self.tabla_receta.setItem(rows, 1, QTableWidgetItem("COSTO TOTAL RECETA:"))
        self.tabla_receta.setItem(rows, 2, QTableWidgetItem(f"${total:.2f}"))

    # Pestaña visor
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
        self.v_text.setStyleSheet("font-size: 24px; line-height: 1.5;")
        
        layout.addLayout(h)
        layout.addWidget(self.v_text)
        tab.setLayout(layout)
        self.tabs.addTab(tab, "RECETARIO")
        
        self.v_prod.currentIndexChanged.connect(self.cargar_tams_visor)
        self.v_tam.currentIndexChanged.connect(self.mostrar_receta)

    def recargar_visor(self):
        self.v_prod.clear()
        for p in self.db.traer_datos("SELECT id, nombre FROM productos"):
            self.v_prod.addItem(p[1], p[0])

    def cargar_tams_visor(self):
        self.v_tam.clear()
        pid = self.v_prod.currentData()
        if not pid: return
        query = "SELECT t.id, t.nombre FROM receta_config rc JOIN tamanos t ON rc.tamano_id = t.id WHERE rc.producto_id=?"
        for t in self.db.traer_datos(query, (pid,)):
            self.v_tam.addItem(t[1], t[0])
        self.mostrar_receta()

    def mostrar_receta(self):
        pid = self.v_prod.currentData()
        tid = self.v_tam.currentData()
        if not pid or not tid: 
            self.v_text.setText("")
            return

        inst = self.db.traer_datos("SELECT instrucciones FROM productos WHERE id=?", (pid,))[0][0]
        
        query = '''
            SELECT i.nombre, r.cantidad_necesaria, u.nombre
            FROM receta_ingredientes r
            JOIN insumos i ON r.insumo_id = i.id
            JOIN unidades u ON i.unidad_uso_id = u.id
            JOIN receta_config rc ON r.receta_config_id = rc.id
            WHERE rc.producto_id = ? AND rc.tamano_id = ?
        '''
        ings = self.db.traer_datos(query, (pid, tid))
        
        html = f"<h2 style='color:#007BFF'>PREPARACIÓN:</h2><p>{inst}</p><hr><h2 style='color:#28a745'>INGREDIENTES:</h2><ul>"
        for ing in ings:
            html += f"<li><b>{ing[0]}:</b> {ing[1]} {ing[2]}</li>"
        html += "</ul>"
        
        self.v_text.setHtml(html)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SistemaCafeApp()
    window.show()
    sys.exit(app.exec_())