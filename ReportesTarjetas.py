import os
import time
import glob
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from urllib3.exceptions import ReadTimeoutError # Importar para captura específica

# Opcional: Importar pandas para combinar CSVs
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("Advertencia: Librería 'pandas' no encontrada. La combinación de CSVs no estará disponible.")
    print("Puedes instalarla con: pip install pandas")

# --- CONFIGURACIÓN ---
download_dir = os.path.abspath("descargas_lotes")
os.makedirs(download_dir, exist_ok=True)
combined_csv_filename = os.path.join(download_dir, "Reporte_Consolidado_Total.csv")


options = Options()
prefs = {
    "download.default_directory": download_dir,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safeBrowse.enabled": True
}
options.add_experimental_option("prefs", prefs)
# Descomenta para modo headless si lo necesitas:
# options.add_argument("--headless")
# options.add_argument("--disable-gpu")
# options.add_argument("--window-size=1920,1080")

driver = None # Inicializar driver a None

# --- PARÁMETROS DE PROCESAMIENTO POR LOTES ---
# Asegúrate que el formato de esta fecha coincida con el que espera la web (DD/MM/YYYY o MM/DD/YYYY)
# El script intentará determinarlo, pero es mejor estar seguro.
fecha_inicio_general_str = "01/01/2024"
fecha_fin_general_dt = datetime.now() # Hasta la fecha actual

# Variable global para el formato de fecha detectado/usado
FORMATO_FECHA_WEB = ""

downloaded_files_list = [] # Para guardar los nombres de los archivos descargados

try:
    # Determinar el formato de fecha de entrada
    try:
        datetime.strptime(fecha_inicio_general_str, "%m/%d/%Y")
        FORMATO_FECHA_WEB = "%m/%d/%Y"
        print(f"Formato de fecha detectado/asumido para la entrada: MM/DD/YYYY")
    except ValueError:
        try:
            datetime.strptime(fecha_inicio_general_str, "%d/%m/%Y")
            FORMATO_FECHA_WEB = "%d/%m/%Y"
            print(f"Formato de fecha detectado/asumido para la entrada: DD/MM/YYYY")
        except ValueError:
            print(f"Error: El formato de 'fecha_inicio_general_str' ('{fecha_inicio_general_str}') no es MM/DD/YYYY ni DD/MM/YYYY.")
            exit()

    fecha_actual_dt = datetime.strptime(fecha_inicio_general_str, FORMATO_FECHA_WEB)

    print(f"Iniciando procesamiento por lotes de 4 meses desde {fecha_actual_dt.strftime(FORMATO_FECHA_WEB)} hasta {fecha_fin_general_dt.strftime(FORMATO_FECHA_WEB)}")

    driver = webdriver.Chrome(options=options)
    driver.get("http://189.206.79.29:13005/aguascalientes/ags_registro_folios/index.php")

    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.NAME, "loginUsername")))
    driver.find_element(By.NAME, "loginUsername").send_keys("Modificar")
    driver.find_element(By.NAME, "loginPassword").send_keys("Mdfcr753")
    driver.find_element(By.ID, "login").click()
    print("Login exitoso.")

    # Bucle principal para procesar por lotes de 4 meses
    while fecha_actual_dt <= fecha_fin_general_dt:
        inicio_lote_dt = fecha_actual_dt

        # Calcular el fin del lote de 4 meses
        # Un período de 4 meses significa mes_actual + 3 meses más.
        # El siguiente período comenzaría 4 meses después del inicio del mes actual.
        
        # Calculamos el primer día del mes que está 4 meses después del inicio_lote_dt
        year_siguiente_periodo = inicio_lote_dt.year
        month_siguiente_periodo = inicio_lote_dt.month + 4 # Sumamos 4 para llegar al inicio del siguiente periodo de 4 meses

        if month_siguiente_periodo > 12:
            year_increment = (month_siguiente_periodo - 1) // 12
            year_siguiente_periodo += year_increment
            month_siguiente_periodo = (month_siguiente_periodo - 1) % 12 + 1
        
        primer_dia_siguiente_lote = datetime(year_siguiente_periodo, month_siguiente_periodo, 1)
        
        # El fin de nuestro lote actual es un día antes del inicio del siguiente lote
        fin_lote_dt = primer_dia_siguiente_lote - timedelta(days=1)

        # Asegurarse de que fin_lote_dt no exceda la fecha_fin_general_dt
        if fin_lote_dt > fecha_fin_general_dt:
            fin_lote_dt = fecha_fin_general_dt

        fecha_inicio_lote_str = inicio_lote_dt.strftime(FORMATO_FECHA_WEB)
        fecha_fin_lote_str = fin_lote_dt.strftime(FORMATO_FECHA_WEB)

        print(f"\n--- Procesando lote: {fecha_inicio_lote_str} - {fecha_fin_lote_str} ---")

        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "fechaConsulta")))
        
        # Limpiar campos y enviar fechas
        campo_fecha_inicio = driver.find_element(By.ID, "fechaConsulta")
        campo_fecha_inicio.clear()
        campo_fecha_inicio.send_keys(fecha_inicio_lote_str)

        campo_fecha_fin = driver.find_element(By.ID, "fechaConsultaFin")
        campo_fecha_fin.clear()
        campo_fecha_fin.send_keys(fecha_fin_lote_str)

        driver.find_element(By.ID, "searchFecha").click()
        print(f"🔍 Búsqueda iniciada para el lote: {fecha_inicio_lote_str} a {fecha_fin_lote_str}.")

        tiempo_de_respiro = 25 # Segundos. Ajusta si es necesario.
        print(f"⏳ Dando un respiro a la página por {tiempo_de_respiro} segundos...")
        time.sleep(tiempo_de_respiro)
        print("✅ Respiro completado. Ahora esperando el botón CSV para el lote.")

        try:
            print("⌛ Esperando a que el botón CSV esté disponible...")
            # Timeout para el botón CSV por lote. Si los lotes son más pequeños, se puede reducir.
            csv_button = WebDriverWait(driver, 240).until( 
                EC.element_to_be_clickable((By.CLASS_NAME, "buttons-csv"))
            )
            print("✅ Botón CSV disponible para el lote.")
            time.sleep(2) # Pequeña pausa antes del clic
            csv_button.click()
            print(f"📥 Clic en el botón CSV realizado.")

            # --- ESPERAR LA DESCARGA DEL ARCHIVO ---
            print("⏳ Esperando la descarga del archivo CSV del lote...")
            start_time_descarga = time.time()
            downloaded_file_lote_path = None
            timeout_descarga_lote = 90 # Segundos para la descarga

            expected_download_name_part = "Folios Telefonicos" # Parte del nombre del archivo que descarga la web

            while time.time() - start_time_descarga < timeout_descarga_lote:
                # Busca cualquier archivo .csv que no sea una descarga parcial
                # y que haya sido modificado/creado recientemente
                current_time = time.time()
                potential_files = []
                for f_name in glob.glob(os.path.join(download_dir, "*.csv")):
                    if not f_name.endswith(".crdownload"):
                        try:
                            file_mod_time = os.path.getctime(f_name)
                            # Considerar archivos creados en los últimos X segundos como candidatos
                            if (current_time - file_mod_time) < 20: # Archivo muy reciente
                                potential_files.append(f_name)
                        except OSError:
                            continue # Archivo podría haber sido borrado mientras tanto

                if potential_files:
                    latest_file_path = max(potential_files, key=os.path.getctime)
                    if os.path.getsize(latest_file_path) > 0: # Asegurarse que no está vacío
                        downloaded_file_lote_path = latest_file_path
                        break
                time.sleep(1)
            
            if downloaded_file_lote_path:
                # Renombrar el archivo descargado para este lote
                new_filename = os.path.join(download_dir, f"Reporte_{inicio_lote_dt.strftime('%Y-%m-%d')}_a_{fin_lote_dt.strftime('%Y-%m-%d')}.csv")
                try:
                    if os.path.exists(new_filename):
                        os.remove(new_filename) # Borrar si ya existe de una ejecución anterior
                    os.rename(downloaded_file_lote_path, new_filename)
                    print(f"✅ Archivo descargado y renombrado para el lote: {new_filename}")
                    downloaded_files_list.append(new_filename)
                except OSError as e:
                    print(f"⚠️ Error al renombrar archivo {downloaded_file_lote_path} a {new_filename}: {e}.")
                    print(f"   El archivo se conservará como {downloaded_file_lote_path}")
                    downloaded_files_list.append(downloaded_file_lote_path) # Guardar el nombre original si falla el renombrado
            else:
                print(f"❌ No se completó la descarga del archivo CSV para el lote ({fecha_inicio_lote_str} - {fecha_fin_lote_str}) después de {timeout_descarga_lote} segundos.")
                # Opcional: Tomar captura si la descarga falla
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_file = os.path.join(download_dir, f"error_descarga_lote_{inicio_lote_dt.strftime('%Y%m%d')}_{timestamp}.png")
                if driver: driver.save_screenshot(screenshot_file)
                print(f"📸 Captura de pantalla por error de descarga guardada en: {screenshot_file}")


        except (TimeoutException, ReadTimeoutError) as e_wait:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_file = os.path.join(download_dir, f"error_CSV_lote_{inicio_lote_dt.strftime('%Y%m%d')}_{timestamp}.png")
            print(f"❌ Error esperando/haciendo clic en botón CSV para el lote ({fecha_inicio_lote_str} - {fecha_fin_lote_str}): {type(e_wait).__name__}")
            if driver:
                try:
                    driver.save_screenshot(screenshot_file)
                    print(f"📸 Captura de pantalla guardada en: {screenshot_file}")
                except Exception as e_shot:
                    print(f"⚠️ No se pudo tomar la captura de pantalla: {e_shot}")
            print("   Continuando con el siguiente lote si es posible...")
            # Podrías decidir detener el script aquí si un lote falla:
            # raise Exception(f"Fallo crítico en el lote {fecha_inicio_lote_str} - {fecha_fin_lote_str}")


        # Avanzar al siguiente período para el lote
        fecha_actual_dt = primer_dia_siguiente_lote
        
        # Si el inicio del siguiente lote ya superó la fecha fin general, terminamos.
        if fecha_actual_dt > fecha_fin_general_dt and inicio_lote_dt.month == fin_lote_dt.month and inicio_lote_dt.year == fin_lote_dt.year : # Condición para el último lote
             break


    print("\n--- Proceso de todos los lotes completado. ---")

    # --- OPCIONAL: COMBINAR TODOS LOS CSVS DESCARGADOS ---
    if PANDAS_AVAILABLE and downloaded_files_list:
        print(f"\nIntentando combinar {len(downloaded_files_list)} archivos CSV descargados...")
        all_dataframes = []
        for f_path in downloaded_files_list:
            try:
                # Asumir que todos los CSVs tienen la misma estructura de columnas
                # Podrías necesitar especificar el encoding si no es utf-8
                df_lote = pd.read_csv(f_path) 
                all_dataframes.append(df_lote)
                print(f"  Archivo '{os.path.basename(f_path)}' leído correctamente.")
            except Exception as e_pandas:
                print(f"  ⚠️ Error al leer el archivo CSV '{f_path}' con pandas: {e_pandas}")
        
        if all_dataframes:
            try:
                consolidated_df = pd.concat(all_dataframes, ignore_index=True)
                
                consolidated_df.to_csv(combined_csv_filename, index=False)
                print(f"✅ Todos los archivos CSV han sido combinados en: {combined_csv_filename}")

                # --- AGREGAR RESUMEN ---
                total_registros = len(consolidated_df)
                registros_no_aplicados = consolidated_df['Modificar'].isna().sum() + (consolidated_df['Modificar'] == "").sum()
                registros_aplicados = (consolidated_df['Modificar'].astype(str).str.strip().str.lower() == "aplicada").sum()

                resumen = [
                    "",
                    f"Resumen del consolidado generado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Total de registros: {total_registros}",
                    f"Registros no aplicados (Modificar vacío): {registros_no_aplicados}",
                    f"Registros aplicados (Modificar = Aplicada): {registros_aplicados}"
                ]

                with open(combined_csv_filename, 'a', encoding='utf-8') as f_out:
                    for linea in resumen:
                        f_out.write(f"{linea}\n")

                print("📝 Resumen agregado al final del archivo consolidado.")

            except Exception as e_concat:
                print(f"💥 Error al concatenar o guardar el DataFrame consolidado: {e_concat}")
        else:
            print("No hay DataFrames para consolidar (posiblemente todos los archivos CSV tuvieron errores de lectura).")

    elif not downloaded_files_list:
        print("No se descargaron archivos CSV para combinar.")

    input("\nPresiona Enter para cerrar el navegador...")

except FileNotFoundError as e_fnf:
    print(f"Error de archivo no encontrado: {e_fnf}. Asegúrate que ChromeDriver esté accesible.")
except Exception as e_global:
    print(f"💥 Ocurrió un error global en el script: {e_global}")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_file = os.path.join(download_dir, f"error_global_{timestamp}.png")
    if driver: # Asegurarse que driver existe
        try:
            driver.save_screenshot(screenshot_file)
            print(f"📸 Captura de pantalla global guardada en: {screenshot_file}")
        except Exception as e_shot:
            print(f"⚠️ No se pudo tomar la captura de pantalla global: {e_shot}")

finally:
    if driver:
        driver.quit()
        print("\n🧹 Navegador cerrado.")