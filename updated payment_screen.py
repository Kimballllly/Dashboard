import RPi.GPIO as GPIO

import time

import tkinter as tk

from threading import Thread

import mysql.connector  # Import MySQL Connector

import subprocess

import os

from PIL import Image, ImageTk

from tkinter import messagebox  # Import messagebox for alert popups

from tkinter import Button



COIN_PIN = 26  # The GPIO pin connected to the COIN wire

GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering

GPIO.setup(COIN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Use internal pull-up resistor



def parse_pages_to_print(pages_to_print):

    """Parses the pages_to_print string and returns a list of page numbers."""

    pages = []

    if pages_to_print.lower() == "all":

        return []  # Represents all pages

    for part in pages_to_print.split(","):

        if "-" in part:

            start, end = map(int, part.split("-"))

            pages.extend(range(start, end + 1))

        else:

            pages.append(int(part))

    return pages





def convert_docx_to_pdf(docx_file_path):

    """Convert .docx file to .pdf using LibreOffice in headless mode."""

    pdf_file_path = docx_file_path.replace(".docx", ".pdf")

    try:

        subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", docx_file_path], check=True)

        print(f"[DEBUG] Converted {docx_file_path} to {pdf_file_path}.")

        return pdf_file_path

    except subprocess.CalledProcessError as e:

        print(f"[ERROR] Failed to convert {docx_file_path} to PDF: {e}")

        return None





def update_printer_status(printer_id, pages_printed):

    """Updates the remaining paper in the printer_status table."""

    try:

        connection = mysql.connector.connect(

            host="paperazzi.cre40o0wmfru.ap-southeast-2.rds.amazonaws.com",

            user="admin",

            password="paperazzi",

            database="paperazzi"

        )

        cursor = connection.cursor()



        # Fetch the current remaining paper count

        select_query = "SELECT remaining_paper FROM printer_status WHERE id = %s"

        cursor.execute(select_query, (printer_id,))

        result = cursor.fetchone()



        if result:

            remaining_paper = result[0]



            if remaining_paper >= pages_printed:

                new_remaining_paper = remaining_paper - pages_printed



                # Update the remaining paper count

                update_query = """

                    UPDATE printer_status

                    SET remaining_paper = %s, updated_at = NOW()

                    WHERE id = %s

                """

                cursor.execute(update_query, (new_remaining_paper, printer_id))

                connection.commit()



                print(f"[DEBUG] Printer ID {printer_id} updated. Remaining paper: {new_remaining_paper}")

            else:

                print(f"[ERROR] Not enough paper in Printer ID {printer_id}. Remaining: {remaining_paper}, Needed: {pages_printed}")

        else:

            print(f"[ERROR] Printer ID {printer_id} not found in the database.")



    except mysql.connector.Error as e:

        print(f"[ERROR] Database error while updating printer status: {e}")

    finally:

        if connection.is_connected():

            cursor.close()

            connection.close()





def print_file(job_id):



    """Fetches the file data and name associated with the job_id from the print_jobs table,

    fetches pages_to_print and color_mode from the print_job_details table, saves it as a 

    temporary file, converts it to PDF if needed, and sends it to the printer with the appropriate color settings."""



    try:

        # Database connection

        connection = mysql.connector.connect(

            host="paperazzi.cre40o0wmfru.ap-southeast-2.rds.amazonaws.com",

            user="admin",

            password="paperazzi",

            database="paperazzi"

        )

        cursor = connection.cursor()

        # Fetch file data, document name, pages_to_print, and color_mode



        select_query = """



            SELECT p.document_name, p.file_data, j.pages_to_print, j.color_mode

            FROM print_jobs p

            JOIN print_job_details j ON p.job_id = j.job_id

            WHERE p.job_id = %s

        """



        cursor.execute(select_query, (job_id,))

        result = cursor.fetchone()



        def get_printer_list():

            try:

                result = subprocess.run(["lpstat", "-p"], capture_output=True, text=True, check=True)

                return [line.split()[1] for line in result.stdout.splitlines() if line.startswith("printer")]

            except subprocess.CalledProcessError as e:

                print(f"[ERROR] Could not retrieve printer list: {e}")

                return []



        printer_name = "Canon_TS200_series_1"



        available_printers = get_printer_list()



        if printer_name not in available_printers:



            print(f"[ERROR] Printer {printer_name} not found. Available printers: {available_printers}")

            return



        if result:

            document_name, file_data, pages_to_print, color_mode = result

            temp_file_path = f"/tmp/{document_name}"  # Save the file in a temporary directory



            # Write file data to a temporary file

            with open(temp_file_path, "wb") as temp_file:

                temp_file.write(file_data)

            print(f"[DEBUG] File saved at {temp_file_path}.")

            # Convert .docx to .pdf if the file is in .docx format

            if temp_file_path.endswith(".docx"):

                pdf_file_path = convert_docx_to_pdf(temp_file_path)

                if pdf_file_path:

                    temp_file_path = pdf_file_path  # Use the PDF file for printing

                else:

                    print("[ERROR] PDF conversion failed. Aborting print.")

                    return

            # Determine page range (if specific pages are provided or "all")

            if pages_to_print.lower() == "all":

                page_range = None  # No page range argument needed for all pages

            else:

                page_range = pages_to_print  # Specific pages like "1-4", "2-2", etc.



            # Determine the color mode

            if color_mode.lower() == "colored":

                color_option = "ColorModel=RGB"  # Color printing

            elif color_mode.lower() == "bw" or color_mode.lower() == "monochrome":

                color_option = "ColorModel=Gray"  # Black-and-white printing

            else:

                print(f"[ERROR] Invalid color mode: {color_mode}")

                return

              # Verify printer existence



            printer_name = "Canon_TS200_series_1"



            available_printers = get_printer_list()



            if printer_name not in available_printers:



                print(f"[ERROR] Printer {printer_name} not found. Available printers: {available_printers}")



                return

          # Base command to print the document with the specified color mode

            command = ["lp", "-d", printer_name, "-o", color_option, temp_file_path]



            if page_range:



                command = ["lp", "-d", printer_name, "-P", page_range, "-o", color_option, temp_file_path]

            print(f"[DEBUG] Sending command to printer: {command}")

            subprocess.run(command, check=True)

            print(f"[DEBUG] File {temp_file_path} sent to the printer successfully.")

            # Clean up temporary files (both original and PDF)

            os.remove(temp_file_path)

            print(f"[DEBUG] Temporary file {temp_file_path} deleted.")

        else:

            print(f"[ERROR] No file found for job ID {job_id}.")

    except mysql.connector.Error as e:

        print(f"[ERROR] Database error: {e}")

    except subprocess.CalledProcessError as e:

        print(f"[ERROR] Printer error: {e}")

    except Exception as e:

        print(f"[ERROR] Unexpected error: {e}")

    finally:

        if connection.is_connected():

            cursor.close()

            connection.close()







def show_payment_screen(total_price, job_id):

    """Displays the payment screen and handles coin detection and printing."""# Function to update the database status to 'cancelled'

     

    root = tk.Tk()

    root.title("Payment Screen")

    root.configure(bg="white")  # Set the background to white



    root.attributes("-fullscreen", True)

    

         # Force fullscreen

    screen_width = root.winfo_screenwidth()

    screen_height = root.winfo_screenheight()

    root.geometry(f"{screen_width}x{screen_height}+0+0")

 



    # Exit fullscreen on ESC

    def exit_fullscreen(event):

        root.destroy()

    total_amount = 0

    timeout = 300  # Timeout in seconds (5 minutes)

   





    def calculate_amount(pulse_count):

        """Calculate the amount in pesos based on the pulse count."""

        return pulse_count  # 1 pulse = 1 peso



    def update_gui(message, color="black"):

        """Update the GUI labels with dynamic messages."""

        status_label.config(text=message, fg=color)



    def timeout_handler():

        """Handle timeout if no coins are inserted."""

        global total_amount

        if total_amount < total_price:

            update_gui("Payment timed out. Resetting...", "red")

            root.after(2000, root.destroy)  # Close the GUI after 2 seconds

            GPIO.cleanup()

            try:

                subprocess.run(["python3", "frame1.py"], check=True)

            except Exception as e:

                print(f"[ERROR] Error launching frame1.py: {e}")

                

    def update_job_status(job_id):

        """Update the job status to complete."""

        try:

            connection = mysql.connector.connect(

                host="paperazzi.cre40o0wmfru.ap-southeast-2.rds.amazonaws.com",

                user="admin",

                password="paperazzi",

                database="paperazzi"

            )

            cursor = connection.cursor()



            # Update query

            update_query = "UPDATE print_job_details SET status = %s, updated_at = NOW() WHERE job_id = %s"

            cursor.execute(update_query, ("complete", job_id))

            connection.commit()



            print(f"[DEBUG] Job ID {job_id} marked as complete in the database.")



        except mysql.connector.Error as e:

            print(f"[ERROR] Database error while updating job status: {e}")



        finally:

            if connection.is_connected():

                cursor.close()

                connection.close()



    def print_job():

        """Start the print job and monitor its progress."""

        try:

            # Update the database with the final inserted amount before printing

            try:

                connection = mysql.connector.connect(

                    host="paperazzi.cre40o0wmfru.ap-southeast-2.rds.amazonaws.com",

                    user="admin",

                    password="paperazzi",

                    database="paperazzi"

                )

                cursor = connection.cursor()



                update_query = """

                    UPDATE print_job_details

                    SET inserted_amount = %s, updated_at = NOW()

                    WHERE job_id = %s

                """

                cursor.execute(update_query, (total_amount, job_id))

                connection.commit()



                print(f"[DEBUG] Final inserted amount for Job ID {job_id} recorded as {total_amount} pesos.")

            except mysql.connector.Error as e:

                print(f"[ERROR] Database error while updating inserted amount: {e}")

            finally:

                if connection.is_connected():

                    cursor.close()

                    connection.close()



            # Proceed with printing

            update_gui("Printing in progress...", "blue")

            print_file(job_id)  # Trigger the print job



            # Monitor print job status

            while True:

                result = subprocess.run(

                    ["lpstat", "-o"], capture_output=True, text=True

                )

                if job_id not in result.stdout:

                    break  # Print job is no longer in the queue

                time.sleep(2)  # Check every 2 seconds



            update_gui("Print complete. Returning to main menu", "green")

            time.sleep(2)  # Allow the user to see the message

            root.destroy()

            subprocess.run(["python3", "frame1.py"], check=True)



        except subprocess.CalledProcessError as e:

            update_gui("Printer error occurred.", "red")

            print(f"[ERROR] Printing error: {e}")

        except Exception as e:

            print(f"[ERROR] Unexpected error during printing: {e}")

        finally:

            GPIO.cleanup()



    def cancel_transaction():

        """Handle transaction cancellation."""

        try:

            # Update the database status to 'cancelled'

            connection = mysql.connector.connect(

                host="paperazzi.cre40o0wmfru.ap-southeast-2.rds.amazonaws.com",

                user="admin",

                password="paperazzi",

                database="paperazzi"

            )

            cursor = connection.cursor()



            update_query = """

                UPDATE print_job_details

                SET status = %s, updated_at = NOW()

                WHERE job_id = %s

            """

            cursor.execute(update_query, ("cancelled", job_id))

            connection.commit()



            print(f"[DEBUG] Job ID {job_id} marked as cancelled in the database.")

        except mysql.connector.Error as e:

            print(f"[ERROR] Database error while updating cancellation status: {e}")

        finally:

            if connection.is_connected():

                cursor.close()

                connection.close()



            # Update the GUI and exit the application

        update_gui("Transaction Cancelled. Returning to main menu...", "red")

        root.after(2000, root.destroy)  # Close the GUI after 2 seconds

        try:

            subprocess.run(["python3", "frame1.py"], check=True)

        except Exception as e:

            print(f"[ERROR] Error launching frame1.py: {e}")







    def coin_detection():

        """Detect coin pulses and update the total amount."""

        global total_amount

        pulse_count = 0

        last_state = GPIO.input(COIN_PIN)

        payment_complete = False



        try:

            while True:

                current_state = GPIO.input(COIN_PIN)



                # Detect falling edge (pulse detection)

                if last_state == GPIO.HIGH and current_state == GPIO.LOW:

                    pulse_count += 1

                    total_amount = calculate_amount(pulse_count)



                    # Update the GUI with the latest inserted amount

                    root.after(0, update_gui, f"Inserted Amount: {total_amount} pesos", "black")



                    # If payment is complete, trigger print but keep detecting coins

                    if not payment_complete and total_amount >= total_price:

                        payment_complete = True

                        root.after(0, update_gui, "Payment Complete! Please wait..", "green")

                        Thread(target=print_job, daemon=True).start()



                last_state = current_state

                time.sleep(0.01)  # Check every 10 ms



        except RuntimeError as e:

            print(f"[ERROR] GPIO error: {e}")

        except KeyboardInterrupt:

            print("\n[DEBUG] Exiting.")

        finally:

            GPIO.cleanup()



    



    # GUI setup

    content_frame = tk.Frame(root, bg="white")  # A frame to hold the content and logo

    content_frame.place(relx=0.5, rely=0.5, anchor="center")  # Center the frame in the root window





    # Frame for the content

    text_frame = tk.Frame(content_frame, bg="white")

    text_frame.pack(side="left", padx=20)  # Align the text to the right of the logo with padding



    # Header Label: Professional and clear

    header_label = tk.Label(

        text_frame,

        text="Insert Coins to Complete Payment",

        font=("Helvetica", 42, "bold"),  # Modern font size

        bg="white",  # Neutral white background

        fg="black",  # Classic black for text

        anchor="center",

    )

    header_label.pack(pady=30)  # Add spacious vertical padding



    # Total Price Label: Clear and neutral

    total_price_label = tk.Label(

        text_frame,

        text=f"Total Price: {total_price} pesos",

        font=("Arial", 36, "bold"),  # Bold for emphasis

        bg="white",  # White for consistency

        fg="black",  # Neutral black for the text

        anchor="center",

    )

    total_price_label.pack(pady=20)  # Add padding for spacing



    # Remaining Balance Label: Red for urgency

    status_label = tk.Label(

        text_frame,

        text=f"Remaining: {total_price} pesos",

        font=("Helvetica", 36, "bold"),  # Bold for clarity

        bg="white",  # Clean white background

        fg="red",  # Red for urgency

        anchor="center",

    )

    status_label.pack(pady=20)



    # Optional: Add a light separator for structure

    separator = tk.Frame(text_frame, height=2, bg="#CCCCCC")  # Light gray separator

    separator.pack(fill="x", pady=15)





    

    # Frame for the footer

    footer_frame = tk.Frame(root, bg="white")  # Separate frame for the footer

    footer_frame.pack(side="bottom", fill="x")  # Stick it to the bottom and stretch horizontally



    # Add a Cancel button to the footer

    cancel_button = tk.Button(

        text_frame,

        text="Cancel",

        font=("Arial", 16, "bold"),

        bg="red",

        fg="white",

        width=20,

        height=2,

        command=cancel_transaction,

    )

    cancel_button.pack(pady=30)  # Place it on the right with padding

    

    footer_label = tk.Label(

        footer_frame,

        text="Thank you for using our service!",

        font=("Helvetica", 20),

        bg="white",

        fg="gray",

    )

    footer_label.pack(pady=10)  # Add vertical padding





    # Ensure GPIO is set before starting the thread

    try:

        GPIO.setmode(GPIO.BCM)

        GPIO.setup(COIN_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    except RuntimeError as e:

        print(f"[ERROR] GPIO initialization error: {e}")

        return



    # Run the coin detection in a separate thread

    coin_thread = Thread(target=coin_detection, daemon=True)

    coin_thread.start()



    # Start the timeout timer

    root.after(timeout * 1000, timeout_handler)



    root.mainloop()





if __name__ == "__main__":

    # Example call to the payment screen function for testing

    show_payment_screen(total_price=5, job_id="12345")

