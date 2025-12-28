import sys
import sqlite3
import math
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTableWidget, QTableWidgetItem, QTabWidget, 
                             QComboBox, QMessageBox, QHeaderView, QSplitter,
                             QFormLayout, QGroupBox, QListWidget, QAbstractItemView, 
                             QTextEdit, QDialog, QGridLayout, QFrame, QInputDialog)
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

class DataBase:
    def __init__(self, db_name="db_recetario.db"):
        self.conn = sqlite3.connect(db_name)
        self.conn.execute("PRAGMA foreign_keys = 1")
        self.cursor = self.conn.cursor()
        self.migracion_inicial()
        self.crear_tablas()

    def migracion_inicial(self):
        # Migración para agregar la columna ID a receta_ingredientes si no existe
        try:
            self.cursor.execute("SELECT id FROM receta_ingredientes LIMIT 1")
        except sqlite3.OperationalError:
            # Si falla, es que no existe el ID. La forma más segura en SQLite es recrear la tabla
            print("Actualizando estructura de tabla ingredientes...")
            self.cursor.execute("CREATE TABLE IF NOT EXISTS receta_ingredientes_new (id INTEGER PRIMARY KEY AUTOINCREMENT, receta_config_id INTEGER, insumo_id INTEGER, cantidad_necesaria REAL)")
            try:
                self.cursor.execute("INSERT INTO receta_ingredientes_new (receta_config_id, insumo_id, cantidad_necesaria) SELECT receta_config_id, insumo_id, cantidad_necesaria FROM receta_ingredientes")
                self.cursor.execute("DROP TABLE receta_ingredientes")
            except: pass
            self.cursor.execute("ALTER TABLE receta_ingredientes_new RENAME TO receta_ingredientes")
            self.conn.commit()

    def crear_tablas(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS categorias (id INTEGER PRIMARY KEY, nombre TEXT)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS tamanos (id INTEGER PRIMARY KEY, nombre TEXT)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS unidades (id INTEGER PRIMARY KEY, nombre TEXT)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS subcategorias (id INTEGER PRIMARY KEY, nombre TEXT, categoria_id INTEGER, FOREIGN KEY(categoria_id) REFERENCES categorias(id))''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS insumos (id INTEGER PRIMARY KEY, nombre TEXT, unidad_compra_id INTEGER, unidad_uso_id INTEGER, cantidad_envase REAL, costo_envase REAL, factor_conversion REAL, rendimiento_total REAL, costo_unitario REAL, FOREIGN KEY(unidad_compra_id) REFERENCES unidades(id), FOREIGN KEY(unidad_uso_id) REFERENCES unidades(id))''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS productos (id INTEGER PRIMARY KEY, nombre TEXT, instrucciones TEXT, categoria_id INTEGER, subcategoria_id INTEGER, FOREIGN KEY(categoria_id) REFERENCES categorias(id), FOREIGN KEY(subcategoria_id) REFERENCES subcategorias(id))''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS receta_pasos (id INTEGER PRIMARY KEY, producto_id INTEGER, orden INTEGER, descripcion TEXT, FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE CASCADE)''')
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS receta_config (id INTEGER PRIMARY KEY, producto_id INTEGER, tamano_id INTEGER, UNIQUE(producto_id, tamano_id), FOREIGN KEY(producto_id) REFERENCES productos(id) ON DELETE CASCADE, FOREIGN KEY(tamano_id) REFERENCES tamanos(id))''')
        
        # Tabla de ingredientes con ID único para manejar duplicados (ej: varios Shots)
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS receta_ingredientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receta_config_id INTEGER, 
            insumo_id INTEGER, 
            cantidad_necesaria REAL, 
            FOREIGN KEY(receta_config_id) REFERENCES receta_config(id) ON DELETE CASCADE, 
            FOREIGN KEY(insumo_id) REFERENCES insumos(id))''')
        
        self.cursor.execute("SELECT count(*) FROM unidades")
        if self.cursor.fetchone()[0] == 0:
            unidades_base = ["Pieza", "Litro", "Galón", "Onza (oz)", "Gramo (gr)", "Mililitro (ml)", "Kilogramo (kg)"]
            for u in unidades_base: self.cursor.execute("INSERT INTO unidades (nombre) VALUES (?)", (u,))
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

    def buscar_insumos(self, texto):
        query = "SELECT i.id, i.nombre, u.nombre FROM insumos i JOIN unidades u ON i.unidad_uso_id = u.id WHERE i.nombre LIKE ?"
        return self.traer_datos(query, (f'%{texto}%',))

# --- Clases ABM ---
class ABMSimple(QWidget):
    def __init__(self, titulo, tabla, db, callback_cambios=None):
        super().__init__()
        self.tabla_bd = tabla; self.db = db; self.id_seleccionado = None; self.callback_cambios = callback_cambios
        layout = QVBoxLayout(); self.group = QGroupBox(titulo); vbox = QVBoxLayout(); h_in = QHBoxLayout()
        self.txt_nombre = QLineEdit(); self.txt_nombre.setPlaceholderText("Nombre..."); h_in.addWidget(self.txt_nombre); vbox.addLayout(h_in)
        h_btns = QHBoxLayout(); self.btn_add = QPushButton("Agregar"); self.btn_add.clicked.connect(self.agregar)
        self.btn_update = QPushButton("Actualizar"); self.btn_update.clicked.connect(self.actualizar); self.btn_update.setEnabled(False)
        self.btn_delete = QPushButton("Eliminar"); self.btn_delete.setStyleSheet("background-color: #dc3545;"); self.btn_delete.clicked.connect(self.eliminar); self.btn_delete.setEnabled(False)
        self.btn_clear = QPushButton("Limpiar"); self.btn_clear.setStyleSheet("background-color: #6c757d;"); self.btn_clear.clicked.connect(self.limpiar)
        h_btns.addWidget(self.btn_add); h_btns.addWidget(self.btn_update); h_btns.addWidget(self.btn_delete); h_btns.addWidget(self.btn_clear); vbox.addLayout(h_btns)
        self.tabla = QTableWidget(); self.tabla.setColumnCount(2); self.tabla.setHorizontalHeaderLabels(["ID", "Nombre"]); self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tabla.hideColumn(0); self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.tabla.itemClicked.connect(self.seleccionar)
        vbox.addWidget(self.tabla); self.group.setLayout(vbox); layout.addWidget(self.group); self.setLayout(layout); self.cargar_datos()

    def cargar_datos(self):
        self.tabla.setRowCount(0)
        for i, (fid, nom) in enumerate(self.db.traer_datos(f"SELECT id, nombre FROM {self.tabla_bd}")):
            self.tabla.insertRow(i); self.tabla.setItem(i, 0, QTableWidgetItem(str(fid))); self.tabla.setItem(i, 1, QTableWidgetItem(nom))

    def seleccionar(self):
        row = self.tabla.currentRow()
        if row >= 0:
            self.id_seleccionado = self.tabla.item(row, 0).text(); self.txt_nombre.setText(self.tabla.item(row, 1).text())
            self.btn_add.setEnabled(False); self.btn_update.setEnabled(True); self.btn_delete.setEnabled(True)

    def limpiar(self):
        self.txt_nombre.clear(); self.id_seleccionado = None; self.tabla.clearSelection()
        self.btn_add.setEnabled(True); self.btn_update.setEnabled(False); self.btn_delete.setEnabled(False)
    
    def notificar(self):
        if self.callback_cambios: self.callback_cambios()

    def agregar(self):
        if self.txt_nombre.text():
            self.db.ejecutar(f"INSERT INTO {self.tabla_bd} (nombre) VALUES (?)", (self.txt_nombre.text(),)); self.limpiar(); self.cargar_datos(); self.notificar()

    def actualizar(self):
        if self.id_seleccionado and self.txt_nombre.text():
            self.db.ejecutar(f"UPDATE {self.tabla_bd} SET nombre=? WHERE id=?", (self.txt_nombre.text(), self.id_seleccionado)); self.limpiar(); self.cargar_datos(); self.notificar()

    def eliminar(self):
        if self.id_seleccionado:
            if QMessageBox.question(self, "Borrar", "¿Seguro?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
                self.db.ejecutar(f"DELETE FROM {self.tabla_bd} WHERE id=?", (self.id_seleccionado,)); self.limpiar(); self.cargar_datos(); self.notificar()

class ABMSubcategorias(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db; self.id_seleccionado = None; layout = QVBoxLayout(); self.group = QGroupBox("Gestión de Subcategorías"); vbox = QVBoxLayout(); form = QFormLayout()
        self.txt_nombre = QLineEdit(); self.cmb_categoria = QComboBox(); form.addRow("Nombre Subcategoría:", self.txt_nombre); form.addRow("Pertenece a Categoría:", self.cmb_categoria); vbox.addLayout(form)
        h_btns = QHBoxLayout(); self.btn_add = QPushButton("Agregar"); self.btn_add.clicked.connect(self.agregar)
        self.btn_update = QPushButton("Actualizar"); self.btn_update.clicked.connect(self.actualizar); self.btn_update.setEnabled(False)
        self.btn_delete = QPushButton("Eliminar"); self.btn_delete.setStyleSheet("background-color: #dc3545;"); self.btn_delete.clicked.connect(self.eliminar); self.btn_delete.setEnabled(False)
        self.btn_clear = QPushButton("Limpiar"); self.btn_clear.setStyleSheet("background-color: #6c757d;"); self.btn_clear.clicked.connect(self.limpiar)
        h_btns.addWidget(self.btn_add); h_btns.addWidget(self.btn_update); h_btns.addWidget(self.btn_delete); h_btns.addWidget(self.btn_clear); vbox.addLayout(h_btns)
        self.tabla = QTableWidget(); self.tabla.setColumnCount(4); self.tabla.setHorizontalHeaderLabels(["ID", "Subcategoría", "Categoría", "id_cat"])
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows); self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tabla.hideColumn(0); self.tabla.hideColumn(3)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.tabla.itemClicked.connect(self.seleccionar); vbox.addWidget(self.tabla); self.group.setLayout(vbox); layout.addWidget(self.group); self.setLayout(layout)
        self.cargar_categorias(); self.cargar_datos()

    def cargar_categorias(self):
        id_actual = self.cmb_categoria.currentData(); self.cmb_categoria.clear()
        for c in self.db.traer_datos("SELECT id, nombre FROM categorias"): self.cmb_categoria.addItem(c[1], c[0])
        if id_actual:
            idx = self.cmb_categoria.findData(id_actual)
            if idx >= 0: self.cmb_categoria.setCurrentIndex(idx)

    def cargar_datos(self):
        self.tabla.setRowCount(0)
        query = 'SELECT s.id, s.nombre, c.nombre, c.id FROM subcategorias s LEFT JOIN categorias c ON s.categoria_id = c.id'
        for i, row in enumerate(self.db.traer_datos(query)):
            self.tabla.insertRow(i); self.tabla.setItem(i, 0, QTableWidgetItem(str(row[0]))); self.tabla.setItem(i, 1, QTableWidgetItem(row[1]))
            self.tabla.setItem(i, 2, QTableWidgetItem(row[2] if row[2] else "Sin Cat")); self.tabla.setItem(i, 3, QTableWidgetItem(str(row[3]) if row[3] else ""))

    def seleccionar(self):
        row = self.tabla.currentRow()
        if row >= 0:
            self.id_seleccionado = self.tabla.item(row, 0).text(); self.txt_nombre.setText(self.tabla.item(row, 1).text())
            id_cat = self.tabla.item(row, 3).text()
            if id_cat: self.cmb_categoria.setCurrentIndex(self.cmb_categoria.findData(int(id_cat)))
            self.btn_add.setEnabled(False); self.btn_update.setEnabled(True); self.btn_delete.setEnabled(True)

    def limpiar(self):
        self.txt_nombre.clear(); self.id_seleccionado = None; self.tabla.clearSelection()
        self.btn_add.setEnabled(True); self.btn_update.setEnabled(False); self.btn_delete.setEnabled(False)

    def agregar(self):
        cat_id = self.cmb_categoria.currentData()
        if self.txt_nombre.text() and cat_id:
            self.db.ejecutar("INSERT INTO subcategorias (nombre, categoria_id) VALUES (?,?)", (self.txt_nombre.text(), cat_id)); self.limpiar(); self.cargar_datos()

    def actualizar(self):
        cat_id = self.cmb_categoria.currentData()
        if self.id_seleccionado and self.txt_nombre.text() and cat_id:
            self.db.ejecutar("UPDATE subcategorias SET nombre=?, categoria_id=? WHERE id=?", (self.txt_nombre.text(), cat_id, self.id_seleccionado)); self.limpiar(); self.cargar_datos()

    def eliminar(self):
        if self.id_seleccionado:
            if QMessageBox.question(self, "Borrar", "¿Seguro?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
                self.db.ejecutar("DELETE FROM subcategorias WHERE id=?", (self.id_seleccionado,)); self.limpiar(); self.cargar_datos()

# --- Aplicación Principal ---
class SistemaCafeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DataBase(); self.setWindowTitle("Sistema Café ERP"); self.setGeometry(50, 50, 1300, 850)
        self.insumo_id_editar = None; self.producto_seleccionado_id = None; self.id_ingrediente_editar = None
        self.tabs = QTabWidget(); self.setCentralWidget(self.tabs)
        self.setStyleSheet("QTabWidget::pane { border: 1px solid #AAA; } QTabBar::tab { background: #EEE; padding: 10px 20px; border-radius: 4px; margin: 1px; } QTabBar::tab:selected { background: #007BFF; color: white; font-weight: bold; } QLabel { font-size: 14px; } QLineEdit, QComboBox, QTableWidget { font-size: 14px; } QPushButton { background-color: #28a745; color: white; padding: 6px; border-radius: 4px; font-weight: bold; } QPushButton:disabled { background-color: #CCC; }")
        self.init_tab_insumos(); self.init_tab_config(); self.init_tab_productos(); self.init_tab_visor()

    def init_tab_insumos(self):
        tab = QWidget(); layout = QHBoxLayout(); form_panel = QGroupBox("Gestión de Insumos"); form_layout = QVBoxLayout()
        self.ins_nombre = QLineEdit(); self.ins_costo = QLineEdit(); self.ins_cant_envase = QLineEdit()
        self.cmb_uni_compra = QComboBox(); self.cmb_uni_uso = QComboBox()
        self.cmb_uni_compra.currentIndexChanged.connect(self.verificar_conversion); self.cmb_uni_uso.currentIndexChanged.connect(self.verificar_conversion)
        self.lbl_factor = QLabel("Conversión:"); self.ins_factor = QLineEdit(); self.container_factor = QWidget(); lay_factor = QHBoxLayout()
        lay_factor.addWidget(self.lbl_factor); lay_factor.addWidget(self.ins_factor); self.container_factor.setLayout(lay_factor); self.container_factor.setVisible(False)
        self.btn_guardar = QPushButton("Guardar Insumo"); self.btn_guardar.clicked.connect(self.guardar_insumo)
        self.btn_cancelar = QPushButton("Cancelar / Limpiar"); self.btn_cancelar.setStyleSheet("background-color: #6c757d;"); self.btn_cancelar.clicked.connect(self.limpiar_formulario_insumos)
        lay_btns = QHBoxLayout(); lay_btns.addWidget(self.btn_guardar); lay_btns.addWidget(self.btn_cancelar)
        fl = QFormLayout(); fl.addRow("Nombre Insumo:", self.ins_nombre); fl.addRow("Costo de Compra ($):", self.ins_costo); fl.addRow("Unidad de Envase (Compra):", self.cmb_uni_compra); fl.addRow("Cantidad en el Envase:", self.ins_cant_envase); fl.addRow("Unidad para Recetas (Uso):", self.cmb_uni_uso)
        form_layout.addLayout(fl); form_layout.addWidget(self.container_factor); form_layout.addLayout(lay_btns); form_layout.addStretch(); form_panel.setLayout(form_layout)
        right_layout = QVBoxLayout(); self.tabla_insumos = QTableWidget(); cols = ["ID", "Insumo", "Envase", "Costo", "Conv.", "Rendimiento", "Costo Unitario"]
        self.tabla_insumos.setColumnCount(len(cols)); self.tabla_insumos.setHorizontalHeaderLabels(cols); self.tabla_insumos.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.tabla_insumos.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tabla_insumos.setSelectionBehavior(QAbstractItemView.SelectRows)
        hbox_crud = QHBoxLayout(); btn_editar = QPushButton("Editar Seleccionado"); btn_editar.setStyleSheet("background-color: #ffc107; color: black;"); btn_editar.clicked.connect(self.cargar_para_editar)
        btn_eliminar = QPushButton("Eliminar Seleccionado"); btn_eliminar.setStyleSheet("background-color: #dc3545;"); btn_eliminar.clicked.connect(self.eliminar_insumo)
        hbox_crud.addWidget(btn_editar); hbox_crud.addWidget(btn_eliminar); right_layout.addWidget(self.tabla_insumos); right_layout.addLayout(hbox_crud)
        layout.addWidget(form_panel, 1); layout.addLayout(right_layout, 2); tab.setLayout(layout); self.tabs.addTab(tab, "INSUMOS"); self.cargar_unidades_combo(); self.cargar_tabla_insumos()

    def cargar_unidades_combo(self):
        id_c_p = self.cmb_uni_compra.currentData(); id_u_p = self.cmb_uni_uso.currentData(); self.cmb_uni_compra.clear(); self.cmb_uni_uso.clear()
        for u in self.db.traer_datos("SELECT id, nombre FROM unidades"): self.cmb_uni_compra.addItem(u[1], u[0]); self.cmb_uni_uso.addItem(u[1], u[0])
        if id_c_p: self.cmb_uni_compra.setCurrentIndex(self.cmb_uni_compra.findData(id_c_p))
        if id_u_p: self.cmb_uni_uso.setCurrentIndex(self.cmb_uni_uso.findData(id_u_p))

    def verificar_conversion(self):
        id_c = self.cmb_uni_compra.currentData(); id_u = self.cmb_uni_uso.currentData()
        if id_c != id_u and id_c is not None:
            self.container_factor.setVisible(True); self.lbl_factor.setText(f"1 {self.cmb_uni_compra.currentText()} equivale a cuántos {self.cmb_uni_uso.currentText()}?:")
        else: self.container_factor.setVisible(False)

    def limpiar_formulario_insumos(self):
        self.ins_nombre.clear(); self.ins_costo.clear(); self.ins_cant_envase.clear(); self.ins_factor.clear(); self.insumo_id_editar = None; self.btn_guardar.setText("Guardar Insumo"); self.btn_guardar.setStyleSheet("background-color: #28a745; color: white;"); self.tabla_insumos.clearSelection()

    def cargar_para_editar(self):
        rows = self.tabla_insumos.selectionModel().selectedRows()
        if not rows: return
        reg = self.db.traer_datos("SELECT * FROM insumos WHERE id=?", (self.tabla_insumos.item(rows[0].row(), 0).text(),))[0]
        self.insumo_id_editar = reg[0]; self.ins_nombre.setText(reg[1]); self.cmb_uni_compra.setCurrentIndex(self.cmb_uni_compra.findData(reg[2])); self.cmb_uni_uso.setCurrentIndex(self.cmb_uni_uso.findData(reg[3])); self.ins_cant_envase.setText(str(reg[4])); self.ins_costo.setText(str(reg[5])); self.ins_factor.setText(str(reg[6])); self.btn_guardar.setText("Actualizar Insumo"); self.btn_guardar.setStyleSheet("background-color: #007bff; color: white;")

    def eliminar_insumo(self):
        rows = self.tabla_insumos.selectionModel().selectedRows()
        if not rows: return
        if QMessageBox.question(self, "Confirmar", "¿Eliminar insumo?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            if self.db.ejecutar("DELETE FROM insumos WHERE id=?", (self.tabla_insumos.item(rows[0].row(), 0).text(),)): self.cargar_tabla_insumos(); self.limpiar_formulario_insumos()

    def guardar_insumo(self):
        try:
            nombre = self.ins_nombre.text(); c_e = float(self.ins_costo.text()); cant_e = float(self.ins_cant_envase.text()); id_c = self.cmb_uni_compra.currentData(); id_u = self.cmb_uni_uso.currentData(); f = float(self.ins_factor.text()) if id_c != id_u else 1.0; r_r = math.floor(cant_e * f)
            if r_r == 0: return QMessageBox.warning(self, "Error", "El rendimiento da 0.")
            c_u = c_e / r_r
            if self.insumo_id_editar is None: self.db.ejecutar('INSERT INTO insumos (nombre, unidad_compra_id, unidad_uso_id, cantidad_envase, costo_envase, factor_conversion, rendimiento_total, costo_unitario) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (nombre, id_c, id_u, cant_e, c_e, f, r_r, c_u))
            else: self.db.ejecutar('UPDATE insumos SET nombre=?, unidad_compra_id=?, unidad_uso_id=?, cantidad_envase=?, costo_envase=?, factor_conversion=?, rendimiento_total=?, costo_unitario=? WHERE id=?', (nombre, id_c, id_u, cant_e, c_e, f, r_r, c_u, self.insumo_id_editar))
            self.limpiar_formulario_insumos(); self.cargar_tabla_insumos(); QMessageBox.information(self, "Listo", f"Operación Exitosa\nCosto por Uso: ${c_u:.4f}")
        except ValueError: QMessageBox.warning(self, "Error", "Revisar los números.")

    def cargar_tabla_insumos(self):
        self.tabla_insumos.setRowCount(0); query = 'SELECT i.id, i.nombre, (i.cantidad_envase || " " || u1.nombre), i.costo_envase, i.factor_conversion, (i.rendimiento_total || " " || u2.nombre), i.costo_unitario FROM insumos i JOIN unidades u1 ON i.unidad_compra_id = u1.id JOIN unidades u2 ON i.unidad_uso_id = u2.id ORDER BY i.id DESC'
        for r, data in enumerate(self.db.traer_datos(query)):
            self.tabla_insumos.insertRow(r)
            for c, val in enumerate(data):
                txt = f"${val:.4f}" if c == 6 else (f"${val:.2f}" if c == 3 else str(val))
                self.tabla_insumos.setItem(r, c, NumericTableWidgetItem(txt) if c in [0,3,4,6] else QTableWidgetItem(txt))

    def init_tab_config(self):
        tab = QWidget(); layout = QGridLayout(); self.abm_subcategorias = ABMSubcategorias(self.db)
        def cb(): self.abm_subcategorias.cargar_categorias(); self.abm_subcategorias.cargar_datos(); self.cargar_cat_prod()
        self.abm_categorias = ABMSimple("Categorías", "categorias", self.db, callback_cambios=cb); self.abm_tamanos = ABMSimple("Tamaños", "tamanos", self.db); self.abm_unidades = ABMSimple("Unidades de Medida", "unidades", self.db)
        layout.addWidget(self.abm_categorias, 0, 0); layout.addWidget(self.abm_subcategorias, 0, 1); layout.addWidget(self.abm_tamanos, 1, 0); layout.addWidget(self.abm_unidades, 1, 1); tab.setLayout(layout); self.tabs.addTab(tab, "CONFIGURACIÓN")

    def init_tab_productos(self):
        tab = QWidget(); layout = QHBoxLayout(); col1 = QGroupBox("1. Seleccionar Producto"); l1 = QVBoxLayout(); self.lista_productos = QTableWidget(); self.lista_productos.setColumnCount(2); self.lista_productos.setHorizontalHeaderLabels(["ID", "Nombre"]); self.lista_productos.hideColumn(0); self.lista_productos.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.lista_productos.setSelectionBehavior(QAbstractItemView.SelectRows); self.lista_productos.setEditTriggers(QAbstractItemView.NoEditTriggers); self.lista_productos.itemClicked.connect(self.seleccionar_producto_crud); l1.addWidget(self.lista_productos); btn_n = QPushButton("Nuevo Producto"); btn_n.clicked.connect(self.limpiar_form_producto); l1.addWidget(btn_n); col1.setLayout(l1)
        col2 = QGroupBox("2. Definir Producto"); l2 = QVBoxLayout(); form_p = QFormLayout(); self.prod_nombre = QLineEdit(); self.prod_cat = QComboBox(); self.prod_subcat = QComboBox(); self.prod_cat.currentIndexChanged.connect(self.filtrar_subcats_prod); form_p.addRow("Nombre:", self.prod_nombre); form_p.addRow("Categoría:", self.prod_cat); form_p.addRow("Subcategoría:", self.prod_subcat); l2.addLayout(form_p); l2.addWidget(QLabel("<b>Pasos de la Receta:</b>")); self.lista_pasos = QListWidget(); l2.addWidget(self.lista_pasos); h_paso = QHBoxLayout(); self.txt_paso = QLineEdit(); self.txt_paso.setPlaceholderText("Describir paso..."); self.txt_paso.returnPressed.connect(self.agregar_paso); btn_ap = QPushButton("+"); btn_ap.setFixedWidth(40); btn_ap.clicked.connect(self.agregar_paso); btn_dp = QPushButton("-"); btn_dp.setFixedWidth(40); btn_dp.clicked.connect(self.borrar_paso); h_paso.addWidget(self.txt_paso); h_paso.addWidget(btn_ap); h_paso.addWidget(btn_dp); l2.addLayout(h_paso); h_bp = QHBoxLayout(); self.btn_guardar_prod = QPushButton("Guardar Producto"); self.btn_guardar_prod.clicked.connect(self.guardar_producto); self.btn_borrar_prod = QPushButton("Eliminar Producto"); self.btn_borrar_prod.setStyleSheet("background-color: #dc3545;"); self.btn_borrar_prod.clicked.connect(self.eliminar_producto); h_bp.addWidget(self.btn_guardar_prod); h_bp.addWidget(self.btn_borrar_prod); l2.addLayout(h_bp); col2.setLayout(l2)
        col3 = QGroupBox("3. Ingredientes por Tamaño"); l3 = QVBoxLayout(); self.lbl_prod_sel = QLabel("Ningún producto seleccionado"); self.lbl_prod_sel.setStyleSheet("color: gray; font-style: italic;"); l3.addWidget(self.lbl_prod_sel); h_tam = QHBoxLayout(); self.sel_tamano = QComboBox(); btn_ht = QPushButton("Ver Tamaño"); btn_ht.clicked.connect(self.cargar_tabla_receta); h_tam.addWidget(self.sel_tamano); h_tam.addWidget(btn_ht); l3.addLayout(h_tam); self.btn_clonar = QPushButton("Copiar receta de otro tamaño"); self.btn_clonar.setStyleSheet("background-color: #17a2b8; color: white;"); self.btn_clonar.clicked.connect(self.clonar_receta_dialogo); l3.addWidget(self.btn_clonar); l3.addWidget(QLabel("<b>Gestión de Insumo:</b>")); h_ing = QHBoxLayout(); self.txt_buscar_insumo = QLineEdit(); self.txt_buscar_insumo.setPlaceholderText("Filtrar..."); self.txt_buscar_insumo.textChanged.connect(self.filtrar_insumos_receta); self.sel_insumo_receta = QComboBox(); self.sel_insumo_receta.setMinimumWidth(150); self.txt_cant_receta = QLineEdit(); self.txt_cant_receta.setPlaceholderText("Cant."); self.lbl_unidad_insumo = QLabel("u."); self.btn_add_ing = QPushButton("+"); self.btn_add_ing.clicked.connect(self.agregar_ingrediente); h_ing.addWidget(self.txt_buscar_insumo); h_ing.addWidget(self.sel_insumo_receta); h_ing.addWidget(self.txt_cant_receta); h_ing.addWidget(self.lbl_unidad_insumo); h_ing.addWidget(self.btn_add_ing); l3.addLayout(h_ing); self.sel_insumo_receta.currentIndexChanged.connect(self.actualizar_lbl_unidad); self.tabla_receta = QTableWidget(); self.tabla_receta.setColumnCount(5); self.tabla_receta.setHorizontalHeaderLabels(["ID_Ing", "ID_Ins", "Insumo", "Cantidad", "Costo"]); self.tabla_receta.hideColumn(0); self.tabla_receta.hideColumn(1); self.tabla_receta.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.tabla_receta.setSelectionBehavior(QAbstractItemView.SelectRows); self.tabla_receta.setEditTriggers(QAbstractItemView.NoEditTriggers); self.tabla_receta.itemClicked.connect(self.cargar_ingrediente_para_editar); l3.addWidget(self.tabla_receta); btn_di = QPushButton("Quitar Insumo Seleccionado"); btn_di.setStyleSheet("background-color: #ffc107; color: black;"); btn_di.clicked.connect(self.borrar_ingrediente)
        l3.addWidget(btn_di); col3.setLayout(l3); col3.setEnabled(False); self.panel_ingredientes = col3; layout.addWidget(col1, 1); layout.addWidget(col2, 2); layout.addWidget(col3, 2); tab.setLayout(layout); self.tabs.addTab(tab, "RECETAS"); self.tabs.currentChanged.connect(self.al_cambiar_tab); self.sel_tamano.currentIndexChanged.connect(self.cargar_tabla_receta)

    def al_cambiar_tab(self, index):
        if index == 0: self.cargar_unidades_combo(); self.cargar_tabla_insumos()
        if index == 1: self.abm_categorias.cargar_datos(); self.abm_tamanos.cargar_datos(); self.abm_unidades.cargar_datos(); self.abm_subcategorias.cargar_categorias(); self.abm_subcategorias.cargar_datos()
        if index == 2: self.cargar_lista_productos(); self.cargar_cat_prod(); self.cargar_combos_ingredientes()
        if index == 3: self.recargar_visor()

    def cargar_cat_prod(self):
        self.prod_cat.clear(); self.prod_cat.addItem("- Sin Categoría -", None)
        for c in self.db.traer_datos("SELECT id, nombre FROM categorias"): self.prod_cat.addItem(c[1], c[0])
        
    def filtrar_subcats_prod(self):
        self.prod_subcat.clear(); self.prod_subcat.addItem("- Sin Subcategoría -", None); c_id = self.prod_cat.currentData()
        if c_id:
            for s in self.db.traer_datos("SELECT id, nombre FROM subcategorias WHERE categoria_id=?", (c_id,)): self.prod_subcat.addItem(s[1], s[0])

    def cargar_lista_productos(self):
        self.lista_productos.setRowCount(0)
        for r, (pid, nom) in enumerate(self.db.traer_datos("SELECT id, nombre FROM productos ORDER BY nombre")):
            self.lista_productos.insertRow(r); self.lista_productos.setItem(r, 0, QTableWidgetItem(str(pid))); self.lista_productos.setItem(r, 1, QTableWidgetItem(nom))

    def limpiar_form_producto(self):
        self.producto_seleccionado_id = None; self.prod_nombre.clear(); self.prod_cat.setCurrentIndex(0); self.prod_subcat.setCurrentIndex(0); self.lista_pasos.clear(); self.lista_productos.clearSelection(); self.panel_ingredientes.setEnabled(False); self.lbl_prod_sel.setText("Nuevo Producto (Sin guardar)"); self.btn_guardar_prod.setText("Crear Producto"); self.btn_borrar_prod.setEnabled(False)

    def seleccionar_producto_crud(self):
        row = self.lista_productos.currentRow()
        if row < 0: return
        pid = int(self.lista_productos.item(row, 0).text()); self.producto_seleccionado_id = pid; data = self.db.traer_datos("SELECT nombre, categoria_id, subcategoria_id FROM productos WHERE id=?", (pid,))[0]; self.prod_nombre.setText(data[0]); self.prod_cat.setCurrentIndex(self.prod_cat.findData(data[1])); self.prod_subcat.setCurrentIndex(self.prod_subcat.findData(data[2])); self.lista_pasos.clear()
        for p in self.db.traer_datos("SELECT descripcion FROM receta_pasos WHERE producto_id=? ORDER BY orden", (pid,)): self.lista_pasos.addItem(p[0])
        self.panel_ingredientes.setEnabled(True); self.lbl_prod_sel.setText(f"Editando: {data[0]}"); self.btn_guardar_prod.setText("Actualizar Producto"); self.btn_borrar_prod.setEnabled(True); self.cargar_tabla_receta()

    def agregar_paso(self):
        if self.txt_paso.text(): self.lista_pasos.addItem(self.txt_paso.text()); self.txt_paso.clear()

    def borrar_paso(self):
        row = self.lista_pasos.currentRow()
        if row >= 0: self.lista_pasos.takeItem(row)

    def guardar_producto(self):
        if not self.prod_nombre.text(): return QMessageBox.warning(self, "Error", "Falta el nombre")
        if self.producto_seleccionado_id is None:
            self.db.ejecutar("INSERT INTO productos (nombre, categoria_id, subcategoria_id) VALUES (?,?,?)", (self.prod_nombre.text(), self.prod_cat.currentData(), self.prod_subcat.currentData())); self.producto_seleccionado_id = self.db.cursor.lastrowid
        else: self.db.ejecutar("UPDATE productos SET nombre=?, categoria_id=?, subcategoria_id=? WHERE id=?", (self.prod_nombre.text(), self.prod_cat.currentData(), self.prod_subcat.currentData(), self.producto_seleccionado_id))
        self.db.ejecutar("DELETE FROM receta_pasos WHERE producto_id=?", (self.producto_seleccionado_id,))
        for i in range(self.lista_pasos.count()): self.db.ejecutar("INSERT INTO receta_pasos (producto_id, orden, descripcion) VALUES (?,?,?)", (self.producto_seleccionado_id, i+1, self.lista_pasos.item(i).text()))
        self.cargar_lista_productos(); self.panel_ingredientes.setEnabled(True); self.btn_guardar_prod.setText("Actualizar Producto"); QMessageBox.information(self, "Éxito", "Producto Guardado")

    def eliminar_producto(self):
        if self.producto_seleccionado_id and QMessageBox.question(self, "Eliminar", "¿Borrar producto y recetas?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            self.db.ejecutar("DELETE FROM productos WHERE id=?", (self.producto_seleccionado_id,)); self.limpiar_form_producto(); self.cargar_lista_productos()

    def cargar_combos_ingredientes(self):
        self.sel_tamano.clear()
        for t in self.db.traer_datos("SELECT id, nombre FROM tamanos"): self.sel_tamano.addItem(t[1], t[0])
        self.filtrar_insumos_receta()

    def filtrar_insumos_receta(self):
        t = self.txt_buscar_insumo.text(); self.sel_insumo_receta.clear(); ings = self.db.buscar_insumos(t) if len(t) >= 1 else self.db.traer_datos("SELECT i.id, i.nombre, u.nombre FROM insumos i JOIN unidades u ON i.unidad_uso_id = u.id")
        for i in ings: self.sel_insumo_receta.addItem(i[1], {"id": i[0], "unidad": i[2]})
        self.actualizar_lbl_unidad()

    def clonar_receta_dialogo(self):
        t_id = self.sel_tamano.currentData(); query = "SELECT DISTINCT t.id, t.nombre FROM receta_config rc JOIN tamanos t ON rc.tamano_id = t.id JOIN receta_ingredientes ri ON ri.receta_config_id = rc.id WHERE rc.producto_id = ? AND t.id != ?"
        tamanos = self.db.traer_datos(query, (self.producto_seleccionado_id, t_id))
        if not tamanos: return QMessageBox.information(self, "Aviso", "No hay otras recetas para copiar.")
        items = [t[1] for t in tamanos]; item, ok = QInputDialog.getItem(self, "Clonar", "Copiar DESDE:", items, 0, False)
        if ok and item: self.ejecutar_clonado(tamanos[items.index(item)][0], t_id)

    def ejecutar_clonado(self, d_id, h_id):
        self.db.ejecutar("INSERT OR IGNORE INTO receta_config (producto_id, tamano_id) VALUES (?,?)", (self.producto_seleccionado_id, h_id)); c_d = self.db.traer_datos("SELECT id FROM receta_config WHERE producto_id=? AND tamano_id=?", (self.producto_seleccionado_id, d_id))[0][0]; c_h = self.db.traer_datos("SELECT id FROM receta_config WHERE producto_id=? AND tamano_id=?", (self.producto_seleccionado_id, h_id))[0][0]
        for row in self.db.traer_datos("SELECT insumo_id, cantidad_necesaria FROM receta_ingredientes WHERE receta_config_id=?", (c_d,)):
            # En clonación usamos INSERT simple para permitir duplicados si el original los tiene
            self.db.ejecutar("INSERT INTO receta_ingredientes (receta_config_id, insumo_id, cantidad_necesaria) VALUES (?, ?, ?)", (c_h, row[0], row[1]))
        self.cargar_tabla_receta()

    def actualizar_lbl_unidad(self):
        d = self.sel_insumo_receta.currentData()
        if d: self.lbl_unidad_insumo.setText(d["unidad"])

    def cargar_ingrediente_para_editar(self):
        row = self.tabla_receta.currentRow()
        if row < 0 or row >= self.tabla_receta.rowCount() - 1: return
        self.id_ingrediente_editar = int(self.tabla_receta.item(row, 0).text())
        ins_id = int(self.tabla_receta.item(row, 1).text())
        cant = self.tabla_receta.item(row, 3).text().split(' ')[0]
        self.txt_buscar_insumo.setText(self.tabla_receta.item(row, 2).text())
        for i in range(self.sel_insumo_receta.count()):
            if self.sel_insumo_receta.itemData(i)['id'] == ins_id: self.sel_insumo_receta.setCurrentIndex(i); break
        self.txt_cant_receta.setText(cant); self.btn_add_ing.setText("Actualizar"); self.btn_add_ing.setStyleSheet("background-color: #007bff;")

    def agregar_ingrediente(self):
        if not self.producto_seleccionado_id: return
        t_id = self.sel_tamano.currentData(); d = self.sel_insumo_receta.currentData(); c = self.txt_cant_receta.text()
        if not d or not c: return
        self.db.ejecutar("INSERT OR IGNORE INTO receta_config (producto_id, tamano_id) VALUES (?,?)", (self.producto_seleccionado_id, t_id)); rc_id = self.db.traer_datos("SELECT id FROM receta_config WHERE producto_id=? AND tamano_id=?", (self.producto_seleccionado_id, t_id))[0][0]
        
        if self.id_ingrediente_editar:
            # Usar el ID único del ingrediente para actualizar la fila específica
            self.db.ejecutar("UPDATE receta_ingredientes SET insumo_id=?, cantidad_necesaria=? WHERE id=?", (d['id'], float(c), self.id_ingrediente_editar))
            self.id_ingrediente_editar = None
        else:
            # Insertar como nueva fila
            self.db.ejecutar("INSERT INTO receta_ingredientes (receta_config_id, insumo_id, cantidad_necesaria) VALUES (?,?,?)", (rc_id, d['id'], float(c)))
        
        self.txt_cant_receta.clear(); self.btn_add_ing.setText("+"); self.btn_add_ing.setStyleSheet("background-color: #28a745;"); self.cargar_tabla_receta()

    def borrar_ingrediente(self):
        row = self.tabla_receta.currentRow()
        if row >= 0 and row < self.tabla_receta.rowCount() - 1:
            # Borrar usando el ID único del ingrediente (columna 0)
            id_ing = self.tabla_receta.item(row, 0).text()
            self.db.ejecutar("DELETE FROM receta_ingredientes WHERE id=?", (id_ing,))
            self.cargar_tabla_receta()

    def cargar_tabla_receta(self):
        # Limpieza total para asegurar que no hay duplicados visuales
        self.tabla_receta.setRowCount(0); self.btn_add_ing.setText("+"); self.btn_add_ing.setStyleSheet("background-color: #28a745;"); self.id_ingrediente_editar = None
        if not self.producto_seleccionado_id or not self.sel_tamano.currentData(): return
        query = 'SELECT ri.id, ri.insumo_id, i.nombre, ri.cantidad_necesaria, u.nombre, i.costo_unitario FROM receta_ingredientes ri JOIN insumos i ON ri.insumo_id = i.id JOIN unidades u ON i.unidad_uso_id = u.id JOIN receta_config rc ON ri.receta_config_id = rc.id WHERE rc.producto_id = ? AND rc.tamano_id = ?'
        datos = self.db.traer_datos(query, (self.producto_seleccionado_id, self.sel_tamano.currentData())); total = 0
        for i, row in enumerate(datos):
            self.tabla_receta.insertRow(i); cp = row[3] * row[5]; total += cp
            # Guardamos IDs en columnas ocultas 0 y 1
            self.tabla_receta.setItem(i, 0, QTableWidgetItem(str(row[0]))); self.tabla_receta.setItem(i, 1, QTableWidgetItem(str(row[1])))
            self.tabla_receta.setItem(i, 2, QTableWidgetItem(row[2])); self.tabla_receta.setItem(i, 3, QTableWidgetItem(f"{row[3]} {row[4]}")); self.tabla_receta.setItem(i, 4, QTableWidgetItem(f"${cp:.2f}"))
        r = self.tabla_receta.rowCount(); self.tabla_receta.insertRow(r); self.tabla_receta.setItem(r, 2, QTableWidgetItem("TOTAL:")); self.tabla_receta.setItem(r, 4, QTableWidgetItem(f"${total:.2f}"))

    def init_tab_visor(self):
        tab = QWidget(); layout = QVBoxLayout(); h = QHBoxLayout(); self.v_prod = QComboBox(); self.v_tam = QComboBox(); self.v_prod.setStyleSheet("font-size: 18px; padding: 5px;"); self.v_tam.setStyleSheet("font-size: 18px; padding: 5px;"); h.addWidget(QLabel("Producto:")); h.addWidget(self.v_prod, 1); h.addWidget(QLabel("Tamaño:")); h.addWidget(self.v_tam, 1); self.v_text = QTextEdit(); self.v_text.setReadOnly(True); layout.addLayout(h); layout.addWidget(self.v_text); tab.setLayout(layout); self.tabs.addTab(tab, "RECETARIO"); self.v_prod.currentIndexChanged.connect(self.cargar_tams_visor); self.v_tam.currentIndexChanged.connect(self.mostrar_receta_final)

    def recargar_visor(self):
        self.v_prod.clear()
        for p in self.db.traer_datos("SELECT id, nombre FROM productos ORDER BY nombre"): self.v_prod.addItem(p[1], p[0])

    def cargar_tams_visor(self):
        self.v_tam.clear(); p_id = self.v_prod.currentData()
        if p_id:
            for t in self.db.traer_datos("SELECT t.id, t.nombre FROM receta_config rc JOIN tamanos t ON rc.tamano_id = t.id WHERE rc.producto_id=?", (p_id,)): self.v_tam.addItem(t[1], t[0])

    def mostrar_receta_final(self):
        p_id = self.v_prod.currentData(); t_id = self.v_tam.currentData()
        if not p_id: return self.v_text.clear()
        p = self.db.traer_datos("SELECT nombre, (SELECT nombre FROM categorias WHERE id=productos.categoria_id) FROM productos WHERE id=?", (p_id,))[0]; html = f"<h1 style='color:#007BFF'>{p[0]}</h1><b>Categoría:</b> {p[1] if p[1] else 'General'}<hr>"
        if t_id:
            html += "<h3 style='color:#28a745'>INGREDIENTES:</h3><ul>"; ings = self.db.traer_datos('SELECT i.nombre, r.cantidad_necesaria, u.nombre, i.costo_unitario FROM receta_ingredientes r JOIN insumos i ON r.insumo_id = i.id JOIN unidades u ON i.unidad_uso_id = u.id JOIN receta_config rc ON r.receta_config_id = rc.id WHERE rc.producto_id = ? AND rc.tamano_id = ?', (p_id, t_id)); costo = 0
            for ing in ings: html += f"<li><b>{ing[0]}:</b> {ing[1]} {ing[2]}</li>"; costo += ing[1] * ing[3]
            html += f"</ul><p><i>Costo: ${costo:.2f}</i></p>"
        html += "<hr><h3 style='color:#17a2b8'>PREPARACIÓN:</h3><ol>"; pasos = self.db.traer_datos("SELECT descripcion FROM receta_pasos WHERE producto_id=? ORDER BY orden", (p_id,))
        for paso in pasos: html += f"<li>{paso[0]}</li>"
        html += "</ol>"; self.v_text.setHtml(html)

if __name__ == '__main__':
    app = QApplication(sys.argv); window = SistemaCafeApp(); window.show(); sys.exit(app.exec_())