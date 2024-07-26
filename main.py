import streamlit as st
import json
from accounting_service_payments_applications import get_bearer_token,create_headers,get_retailer_id,create_payment,payment_application,search_invoices,get_pmt_transaction_number,filter_dataframe,df_cash,df_checks,df_eft,logs_consolidated
import pandas as pd
import numpy as np
import time
import datetime as dt

st.set_page_config('Payment Application Accounting Service',
                    page_icon= ':bank:',
                    layout= 'wide'
                    )

st.title(':orange[Nabis] Payment Application Accounting Service')

@st.cache_data
def load_dataframe(file):
    """
    Loads the uploaded file into a Pandas DataFrame.
    """

    file_extension = file.name.split(".")[-1]
    
    if file_extension == "csv":
        df = pd.read_csv(file)

    elif file_extension == "xlsx":
        df = pd.read_excel(file)

    return df



intercompany_map = {'1. Nabitwo Checking':'NABITWO',
'4. Nabifive Checking':'NABIFIVE',
'NabiTwo':'NABITWO',
'NabiFive':'NABIFIVE',
'North Hollywood':'NABIFIVE',
'Oakland':'NABIFIVE',
'Woodlake':'NABIFIVE',}

st.cache_data()
cashlog_complete,cashlog = df_cash()
st.session_state['cashlog_complete'] = cashlog_complete
st.session_state['cashlog'] = cashlog
cashlog

st.cache_data()
checklog_complete,checklog = df_checks()
st.session_state['checklog_complete'] = checklog_complete
st.session_state['checklog'] = checklog
checklog


st.cache_data()
eftlog_complete,eftlog = df_eft()
st.session_state['eftlog_complete'] = eftlog_complete
st.session_state['eftlog'] = eftlog
eftlog

st.cache_data()
logs_concatenated_filter = logs_consolidated(cashlog,checklog,eftlog)
logs_concatenated_filter['Intercompany'] = logs_concatenated_filter['Company'].map(intercompany_map)
st.session_state['logs_concatenated_filter'] = logs_concatenated_filter


st.cache_data()
def payments_creation_as(list_payments,headers):
    create_payment_start_time = time.perf_counter()
    
    create_payment(list_payments,headers)
    create_payment_end_time = time.perf_counter()
    create_pmt_execution_time = create_payment_end_time - create_payment_start_time
    st.success(f'Payments Processed, Execution time: {create_pmt_execution_time} seconds' , icon="✅")


st.cache_data()
def application_of_payments(df_invs,headers):
    start_time = time.perf_counter()

    list_data_invs = []  
    for i in df_invs:
        try:
            data_pmt_tid = get_pmt_transaction_number(headers, i)
            
        except Exception as e:
            st.write(e)
            i['pmt_tid'] = 'Payment Not Found'
            continue    
        i['pmt_tid'] = data_pmt_tid
        list_data_invs.append(i)
    
    
    payment_application_list = []
    for pmt_item in list_data_invs:
        dict_temp_apps = {}
        amount_to_apply = round(pmt_item['Amt_to_apply'],ndigits=2)
        dict_temp_apps['pmt_tid'] = pmt_item['pmt_tid']
        utc_str = 'T12:00:00.000Z'
        appliedAt = pmt_item['Applied_At'] + utc_str
        try:
            data_inv_num = search_invoices(pmt_item['Invoice_number'],headers)
        except Exception as e:
            st.write(e)
            st.write(f'order: {pmt_item["Invoice_number"]} not found')    
        invs_nabis = data_inv_num['data']['getAccountingAPIDetailedInvoicesByNumber']['matchingOrderNumber']
        dict_temp_apps['amount_to_apply'] = amount_to_apply
        dict_temp_apps['orders'] = invs_nabis


        iteration_list = []

        for invoice in invs_nabis:
            
            dict_temp_apps_iteration = {}
            dict_temp_apps_iteration['invoiceNumber'] = invoice['invoiceNumber']

            if invoice["invoiceGroupType"] == "ORDER" and invoice["invoiceCollectedRemaining"] > 0:
                if amount_to_apply >= invoice["invoiceCollectedRemaining"]:
                    dict_temp_apps_iteration['amount'] = invoice['invoiceCollectedRemaining']
                    amount_to_apply -= invoice["invoiceCollectedRemaining"]
                    appliedAt = str(appliedAt)
                    dict_temp_apps_iteration['appliedAt'] = appliedAt
                    iteration_list.append(dict_temp_apps_iteration)
                else:
                    dict_temp_apps_iteration['amount'] = amount_to_apply
                    appliedAt = str(appliedAt)
                    dict_temp_apps_iteration['appliedAt'] = appliedAt
                    amount_to_apply = 0
                    iteration_list.append(dict_temp_apps_iteration)

        dict_temp_apps['applications'] = iteration_list
        payment_application_list.append(dict_temp_apps)


    st.markdown('---')
    
    items_status = {}
    for idx,item in enumerate(payment_application_list):
    
        if item['pmt_tid'] != 'Payment Not Found':
            if item['applications'] != None:
                data = payment_application(item,headers)
                
                try:
                    if data['data']['postAccountingAPIApplyTransaction'] == True:
                        order_num = item["orders"][0]["orderNumber"]
                        items_status[order_num] = 'Processed' 
                        
                    else:
                        order_num = item["orders"][0]["orderNumber"]
                        items_status[order_num] =  'Failed'
                                     
                except Exception as e:
                    st.write(e)
                    st.write(f'Order Number: {item["orders"][0]["orderNumber"]}: {data["errors"][0]["message"]}')

                time.sleep(0.1)        
                    

    end_time = time.perf_counter()
        


    for item in payment_application_list:
        if item['pmt_tid'] == 'Payment Not Found':
            st.write('Review the following customer Names, try removing square brackets or spelling')
            st.write(item['orders'][0]['retailerName'])


    execution_time = end_time - start_time
    st.success(f'Applications Completed, Execution time: {execution_time} seconds' , icon="✅")

    df_items_processed = pd.DataFrame(list(items_status.items()), columns=['Order', 'Status'])
    
    return df_items_processed


if __name__ == "__main__":
    with st.form(key='log_in',):
        
        email = st.text_input('email:'),
        password_st = st.text_input('Password:',type='password')

        submitted = st.form_submit_button('Log in')

        try:
            if submitted:
                st.cache_data()
                token,user_id = get_bearer_token(email[0],password_st)
                
                st.cache_data()
                headers = create_headers(token)
                st.session_state['headers'] = headers
                
                st.cache_data()
                data_retailer = get_retailer_id(st.session_state['headers'])
                data_retailer_list = pd.DataFrame()

                for item in data_retailer:
                    df_temp = pd.DataFrame(item,index=[0])
                    data_retailer_list = pd.concat([data_retailer_list,df_temp],ignore_index=True)

                st.session_state['retailers_list'] = data_retailer_list
        except:
            st.write('Credentials are incorrect, Please try again')  
          
    trans_1,trans_2 = st.columns(2)

    with trans_1:
        st.text('What is the transaction you are performing?')
        selection = st.selectbox('Transactions:',options=['None','Payments_Applications','Upload_File'],placeholder='Select an Option')

    if selection == 'None':
      st.write('Please select an option')
        
    elif selection == 'Payments_Applications':
        st.text('Generate Data Frame to work with by Selecting the Date Ranges you want to process')
        df = filter_dataframe(st.session_state['logs_concatenated_filter'],'Logs')

       
        headers = st.session_state['headers']

        payments = df.loc[df['Amount']!='-'].copy()
        payments = payments[['Date','Payment Reference','Amount','Retailer','Nabis Status','Pmt_Method','Intercompany']]
        payments.drop_duplicates(subset=['Payment Reference'],inplace=True)
        
        st.write(f'{payments.shape[0]} Payments to generate')

        mask_invs = ['OP','CREDIT']
        invoices_df = df.loc[~df['Invoices'].isin(mask_invs)].copy()
        invoices_df['Invoices'] = invoices_df['Invoices'].astype('str')
        st.write(f'{invoices_df.shape[0]} Invoices to process')

        invoices_df
        if len(invoices_df['Invoices']) > 0:
            list_invoices = []
            for i in invoices_df['Invoices']:
                item = int(i)
                try:    
                    data = search_invoices(item,headers)
                    list_invoices.append(data)
                except:
                    continue
    
            df_temp_orders = pd.DataFrame()

            for order in list_invoices:
                order_found = order['data']['getAccountingAPIDetailedInvoicesByNumber']['matchingOrderNumber']
                if order_found != None:
                    for idx,item in enumerate(order_found):
                        df_temp = pd.DataFrame(item,index=[0])
                        df_temp_orders = pd.concat([df_temp_orders,df_temp],ignore_index=True)
                    
            
            df_temp_orders_filter = df_temp_orders.loc[df_temp_orders['invoiceGroupType'] == 'ORDER'].copy()
            df_temp_orders_filter['orderNumber'] = df_temp_orders_filter['orderNumber'].astype('str')
            dict_retailerName = dict(zip(df_temp_orders_filter['orderNumber'],df_temp_orders_filter['retailerName']))

        invoices_df['RetailerName'] = invoices_df['Invoices'].map(dict_retailerName)
        dict_pmts_retailer = dict(zip(invoices_df['Payment Reference'], invoices_df['RetailerName']))
        payments['RetailerName'] = payments['Payment Reference'].map(dict_pmts_retailer)
        df_retailers = st.session_state['retailers_list']
        dict_retailers_ID = dict(zip(df_retailers['name'],df_retailers['id']))
        payments['Retailer'] = np.where(payments['Retailer']=='-','Nabione, Inc.',payments['Retailer'])
        payments['Retailer_ID'] = np.where(payments['RetailerName'].isnull(), payments['Retailer'].map(dict_retailers_ID),payments['RetailerName'].map(dict_retailers_ID))
        payments['Location'] = np.where(((payments['Pmt_Method']=='Cash') | (payments['Pmt_Method']=='Check') ) & (payments['Payment Reference'].str.contains('LA')), 'LA',
                                        np.where(((payments['Pmt_Method']=='Cash') | (payments['Pmt_Method']=='Check') ) & (payments['Payment Reference'].str.contains('OAK')), 'OAK',
                                                    np.where((payments['Pmt_Method']=='Check') & (payments['Payment Reference'].str.contains('WL')), 'WL',
                                                            np.where((payments['Pmt_Method']=='Cash') & (payments['Payment Reference'].str.contains('WOOD')), 'WL',
                                                                    np.where((payments['Pmt_Method']=='Check') & (payments['Payment Reference'].str.contains('SF')), 'SF', None)))))


        payments['Payment_Date'] = payments['Date'].dt.date.astype(str)
        payments['Type'] = 'Payment'
        payments['AdminNotes'] = ''
        payments['Retailer_name'] = payments['RetailerName']
        payments['Pmt_Ref'] = payments['Payment Reference'].astype(str)
        payments['pmt_Amount'] = pd.to_numeric(payments['Amount']).round(2)
        payments['Intercompany'] = payments['Intercompany'].astype(str)
        

        invoices_df['Amt_to_apply'] = pd.to_numeric(invoices_df['Amount Applied']).round(2)
        invoices_df['Applied_At'] = invoices_df['Date'].dt.date.astype(str)
        invoices_df['Invoice_number'] = invoices_df['Invoices'].astype(int)
        invoices_df['Pmt_Ref'] = invoices_df['Payment Reference'].astype(str)

        list_pmts = payments.to_json(orient='records')
        list_pmts = json.loads(list_pmts)
        st.session_state['pmts'] = list_pmts

        invs_df_json = invoices_df.to_json(orient='records')
        invs_df_json = json.loads(invs_df_json)
        st.session_state['invs'] = invs_df_json

        submit_to_process = st.button('Create Payments')

        if submit_to_process:
            headers = st.session_state['headers']
            list_pmts = st.session_state['pmts']
            payments_creation_as(list_pmts,headers)                


        applications_button = st.button('Apply Payments')

        if applications_button:
            headers = st.session_state['headers']
            invs_df_json = st.session_state['invs']
            df_items_processed = application_of_payments(df_invs=invs_df_json,headers=headers)
            df_items_processed


    elif selection == 'Upload_File':
       
        col1,col2 = st.columns(2)

        with col1:
            file_uploaded = st.file_uploader('Upload Template file with payments and invoices details')
            
        if file_uploaded:
            
            df_data_pmts = load_dataframe(file_uploaded)
            df_data_pmts['Payment_Date'] = df_data_pmts['Payment_Date'].astype(str)
            df_data_pmts['Pmt_Ref'] = df_data_pmts['Pmt_Ref'].astype(str)
            df_data_pmts['Intercompany'] = df_data_pmts['Intercompany'].astype(str)
            df_data_pmts['pmt_Amount'] = pd.to_numeric(df_data_pmts['pmt_Amount']).round(2)
            df_data_pmts['Amt_to_apply'] = pd.to_numeric(df_data_pmts['Amt_to_apply']).round(2)
            transactions_types = ['Payment', 'Self_Collected', 'Write_Off_Nabis', 'Write_Off_External' , 'Bounced_Check']
            data_pmts_list = df_data_pmts.loc[df_data_pmts['Type'].isin(transactions_types)].copy()
            num_of_pmts = data_pmts_list[data_pmts_list['Type']=='Payment'].shape
            num_of_sc = data_pmts_list[data_pmts_list['Type']=='Self_Collected'].shape
            num_of_wo = data_pmts_list[(data_pmts_list['Type']=='Write_Off_Nabis') | (data_pmts_list['Type']=='Write_Off_External')].shape
            num_of_bc = data_pmts_list[data_pmts_list['Type']=='Bounced_Check'].shape
            st.write(f'Total Number of payments to process is: {num_of_pmts[0]}')
            st.write(f'Total Number of Self Collected to process is: {num_of_sc[0]}')
            st.write(f'Total Number of Write Off to process is: {num_of_wo[0]}')
            st.write(f'Total Number of Bounced Checks to process is: {num_of_bc[0]}')
            list_pmts = data_pmts_list.to_json(orient='records')
            list_pmts = json.loads(list_pmts)

            invoices_list = df_data_pmts.loc[df_data_pmts['Type']=='Invoice'].copy()
            num_of_invs = invoices_list.shape
            st.write(f'Total Number of Invoices to process is: {num_of_invs[0]}')
            invoices_list['Invoice_number'] = invoices_list['Invoice_number'].astype(int)
            invoices_list['Applied_At'] = invoices_list['Applied_At'].astype(str)
            df_invs_json = invoices_list.to_json(orient='records')
            df_invs_json = json.loads(df_invs_json)
            
            submit_to_process = st.button('Create Payments')

            if submit_to_process:
                headers = st.session_state['headers']
                payments_creation_as(list_pmts,headers)                


            applications_button = st.button('Apply Payments')

            if applications_button:
                headers = st.session_state['headers']
                df_items_processed = application_of_payments(df_invs=df_invs_json,headers=headers)
                df_items_processed
               
