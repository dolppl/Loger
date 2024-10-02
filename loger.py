import streamlit as st
import pandas as pd
import re
import gzip
import plotly.express as px

st.set_page_config(layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: show;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True
)

if 'data' not in st.session_state:
    st.session_state['data'] = None

if 'df_filtered' not in st.session_state:
    st.session_state['df_filtered'] = None

st.title('Analiza Logów Serwerowych')

tab1, tab2, tab3, tab4 = st.tabs(['Ładowanie plików', 'Podsumowanie', 'Analizy', 'Szczegóły'])

with tab1:
    st.header('Ładowanie plików')
    uploaded_files = st.file_uploader("Wybierz pliki logów", type=["log", "txt", "gz"], accept_multiple_files=True)

    if uploaded_files:
        data_list = []
        progress_bar = st.progress(0)  
        total_files = len(uploaded_files)  

        for index, uploaded_file in enumerate(uploaded_files):
            progress_bar.progress((index + 1) / total_files)

            if uploaded_file.name.endswith('.gz'):
                with gzip.open(uploaded_file, 'rt', encoding='utf-8') as f:
                    content = f.read()
            else:
                content = uploaded_file.read().decode('utf-8', errors='ignore')

            lines = content.strip().split('\n')

            pattern = r'(?P<ip>\S+) \S+ \S+ \[(?P<datetime>.*?)\] "(?P<method>\S+)(?: (?P<url>.*?))(?: (?P<protocol>HTTP/\d\.\d))?" (?P<status>\d{3}(?:\.\d+)?) (?P<size>\d+|-) "(?P<referrer>.*?)" "(?P<user_agent>.*?)"'

            for line in lines:
                match = re.match(pattern, line)
                if match:
                    data_list.append(match.groupdict())

        if data_list:
            df = pd.DataFrame(data_list)
            df['datetime'] = pd.to_datetime(df['datetime'], format='%d/%b/%Y:%H:%M:%S %z', errors='coerce')
            df['status'] = df['status'].astype(str)
            df['size'] = pd.to_numeric(df['size'], errors='coerce')

            bot_patterns = {
                'Googlebot': r'Googlebot',
                'Bingbot': r'Bingbot',
                'YandexBot': r'YandexBot',
                'AhrefsBot': r'AhrefsBot',
                'DuckDuckBot': r'DuckDuckBot',
                'Baiduspider': r'Baiduspider',
                'MJ12bot': r'MJ12bot',
                'SemrushBot': r'SemrushBot',
                'Sogou': r'Sogou',
                'Exabot': r'Exabot',
                'facebookexternalhit': r'facebookexternalhit',
                'Facebot': r'Facebot',
                'ia_archiver': r'ia_archiver',
            }

            def identify_bot(user_agent):
                for bot_name, bot_pattern in bot_patterns.items():
                    if re.search(bot_pattern, user_agent, re.I):
                        return bot_name
                return 'Inny' 

            df['Bot'] = df['user_agent'].apply(identify_bot)

            st.session_state['data'] = df  
            st.success('Pomyślnie przetworzono pliki.')
        else:
            st.error('Nie udało się sparsować plików logów.')

        progress_bar.empty()  
    else:
        st.info('Proszę załadować pliki logów.')

with st.sidebar:
    st.header("Filtry")
    if st.session_state['data'] is not None:
        df = st.session_state['data']
        min_date = df['datetime'].min()
        max_date = df['datetime'].max()
        if pd.isnull(min_date) or pd.isnull(max_date):
            st.error("Dane nie zawierają poprawnych wartości daty. Sprawdź pliki logów.")
        else:
            date_range = st.date_input(
                "Zakres dat",
                [min_date.date(), max_date.date()],
                min_value=min_date.date(),
                max_value=max_date.date()
            )
            status_options = df['status'].unique()
            selected_status = st.multiselect("Kody statusu", options=status_options, default=list(status_options))
            method_options = df['method'].unique()
            selected_methods = st.multiselect("Metody HTTP", options=method_options, default=list(method_options))
            bot_options = df['Bot'].unique()
            selected_bots = st.multiselect("Boty", options=bot_options, default=list(bot_options))
            df_filtered = df[
                (df['datetime'].dt.date >= date_range[0]) &
                (df['datetime'].dt.date <= date_range[1]) &
                (df['status'].isin(selected_status)) &
                (df['method'].isin(selected_methods)) &
                (df['Bot'].isin(selected_bots))
            ]
            st.session_state['df_filtered'] = df_filtered
with tab2:
    if st.session_state['data'] is None:
        st.warning('Najpierw załaduj pliki w zakładce "Ładowanie plików".')
    else:
        st.header('Podsumowanie')
        df_filtered = st.session_state['df_filtered']
        total_requests = len(df_filtered)
        unique_ips = df_filtered['ip'].nunique()
        total_errors = df_filtered[df_filtered['status'].str.startswith(('4', '5'))].shape[0]
        total_bots = df_filtered[df_filtered['Bot'] != 'Inny'].shape[0]
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Całkowita liczba żądań", total_requests)
        col2.metric("Unikalne adresy IP", unique_ips)
        col3.metric("Liczba błędów", total_errors)
        col4.metric("Liczba żądań botów", total_bots)
with tab3:
    if st.session_state['data'] is None:
        st.warning('Załaduj dane, aby zobaczyć analizy.')
    else:
        st.header('Analizy')
        df_filtered = st.session_state['df_filtered']
        df_time = df_filtered.copy()
        df_time.set_index('datetime', inplace=True)
        st.subheader('Rozkład kodów statusu HTTP')
        status_counts = df_filtered['status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Liczba']
        status_counts = status_counts.sort_values('Status')
        fig_status = px.bar(status_counts, x='Status', y='Liczba', title='Rozkład kodów statusu', text='Liczba')
        fig_status.update_xaxes(type='category')
        st.plotly_chart(fig_status)
        st.subheader('Rozkład kodów statusu w czasie')
        status_time = df_time.groupby([pd.Grouper(freq='D'), 'status']).size().reset_index(name='Liczba')
        fig_status_time = px.line(status_time, x='datetime', y='Liczba', color='status', title='Kody statusu w czasie')
        st.plotly_chart(fig_status_time)
        st.subheader('Najczęściej odwiedzane strony')
        top_urls = df_filtered['url'].value_counts().reset_index().head(10)
        top_urls.columns = ['URL', 'Liczba']
        fig_urls = px.bar(top_urls, x='URL', y='Liczba', title='Top 10 URL', text='Liczba')
        st.plotly_chart(fig_urls)
        st.subheader('Najczęściej odwiedzane strony w czasie')
        top_urls_list = top_urls['URL'].tolist()
        urls_time = df_time[df_time['url'].isin(top_urls_list)].groupby([pd.Grouper(freq='D'), 'url']).size().reset_index(name='Liczba')
        fig_urls_time = px.line(urls_time, x='datetime', y='Liczba', color='url', title='Top URL w czasie')
        st.plotly_chart(fig_urls_time)
        st.subheader('Aktywność w czasie')
        hits_per_hour = df_time.resample('H').size().reset_index(name='Liczba żądań')
        fig_time = px.line(hits_per_hour, x='datetime', y='Liczba żądań', title='Liczba żądań na godzinę')
        st.plotly_chart(fig_time)
        st.subheader('Najczęstsze adresy IP')
        top_ips = df_filtered['ip'].value_counts().reset_index().head(10)
        top_ips.columns = ['IP', 'Liczba']
        fig_ips = px.bar(top_ips, x='IP', y='Liczba', title='Top 10 adresów IP', text='Liczba')
        st.plotly_chart(fig_ips)
        st.subheader('Aktywność top 10 IP w czasie')
        top_ips_list = top_ips['IP'].tolist()
        ips_time = df_time[df_time['ip'].isin(top_ips_list)].groupby([pd.Grouper(freq='D'), 'ip']).size().reset_index(name='Liczba')
        fig_ips_time = px.line(ips_time, x='datetime', y='Liczba', color='ip', title='Aktywność IP w czasie')
        st.plotly_chart(fig_ips_time)
        st.subheader('Rozkład metod HTTP')
        method_counts = df_filtered['method'].value_counts().reset_index()
        method_counts.columns = ['Metoda', 'Liczba']
        fig_methods = px.pie(method_counts, names='Metoda', values='Liczba', title='Metody HTTP')
        st.plotly_chart(fig_methods)
        st.subheader('Rozkład metod HTTP w czasie')
        methods_time = df_time.groupby([pd.Grouper(freq='D'), 'method']).size().reset_index(name='Liczba')
        fig_methods_time = px.line(methods_time, x='datetime', y='Liczba', color='method', title='Metody HTTP w czasie')
        st.plotly_chart(fig_methods_time)
        st.subheader('Najczęściej odwiedzające boty')
        bot_counts = df_filtered[df_filtered['Bot'] != 'Inny']['Bot'].value_counts().reset_index()
        bot_counts.columns = ['Bot', 'Liczba']
        fig_bots = px.bar(bot_counts, x='Bot', y='Liczba', title='Boty', text='Liczba')
        st.plotly_chart(fig_bots)
        st.subheader('Aktywność botów w czasie')
        bots_time = df_time[df_time['Bot'] != 'Inny'].groupby([pd.Grouper(freq='D'), 'Bot']).size().reset_index(name='Liczba')
        fig_bots_time = px.line(bots_time, x='datetime', y='Liczba', color='Bot', title='Aktywność botów w czasie')
        st.plotly_chart(fig_bots_time)
        st.subheader('Najpopularniejsze user agent')
        top_agents = df_filtered['user_agent'].value_counts().reset_index().head(10)
        top_agents.columns = ['User-Agent', 'Liczba']
        st.table(top_agents)
        st.subheader('Aktywność user agent w czasie')
        top_agents_list = top_agents['User-Agent'].tolist()
        agents_time = df_time[df_time['user_agent'].isin(top_agents_list)].groupby([pd.Grouper(freq='D'), 'user_agent']).size().reset_index(name='Liczba')
        fig_agents_time = px.line(agents_time, x='datetime', y='Liczba', color='user_agent', title='Aktywność agentów w czasie')
        st.plotly_chart(fig_agents_time)
        st.subheader('Najpopularniejsze odsyłacze')
        top_referrers = df_filtered['referrer'].value_counts().reset_index().head(10)
        top_referrers.columns = ['Referrer', 'Liczba']
        st.table(top_referrers)
        st.subheader('Aktywność odsyłaczy w czasie')
        top_referrers_list = top_referrers['Referrer'].tolist()
        referrers_time = df_time[df_time['referrer'].isin(top_referrers_list)].groupby([pd.Grouper(freq='D'), 'referrer']).size().reset_index(name='Liczba')
        fig_referrers_time = px.line(referrers_time, x='datetime', y='Liczba', color='referrer', title='Aktywność odsyłaczy w czasie')
        st.plotly_chart(fig_referrers_time)
        st.subheader('Błędy (kody 4xx i 5xx)')
        error_df = df_filtered[df_filtered['status'].str.startswith(('4', '5'))]
        error_counts = error_df['status'].value_counts().reset_index()
        error_counts.columns = ['Status', 'Liczba']
        error_counts = error_counts.sort_values('Status')
        fig_errors = px.bar(error_counts, x='Status', y='Liczba', title='Rozkład błędów', text='Liczba')
        fig_errors.update_xaxes(type='category')
        st.plotly_chart(fig_errors)
        st.subheader('Błędy w czasie')
        errors_time = error_df.set_index('datetime').groupby([pd.Grouper(freq='D'), 'status']).size().reset_index(name='Liczba')
        fig_errors_time = px.line(errors_time, x='datetime', y='Liczba', color='status', title='Błędy w czasie')
        st.plotly_chart(fig_errors_time)
        st.subheader('Średni rozmiar odpowiedzi')
        avg_size = df_filtered['size'].mean()
        st.metric("Średni rozmiar odpowiedzi (bytes)", f"{avg_size:.2f}")
        st.subheader('Średni rozmiar odpowiedzi w czasie')
        size_time = df_time.resample('D')['size'].mean().reset_index()
        size_time.columns = ['Czas', 'Średni rozmiar']
        fig_size_time = px.line(size_time, x='Czas', y='Średni rozmiar', title='Średni rozmiar odpowiedzi w czasie')
        st.plotly_chart(fig_size_time)

with tab4:
    if st.session_state['data'] is None:
        st.warning('Załaduj dane, aby zobaczyć szczegóły.')
    else:
        st.header('Szczegóły')
        df_filtered = st.session_state['df_filtered']
        st.dataframe(df_filtered)
        csv = df_filtered.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Pobierz dane jako CSV",
            data=csv,
            file_name='logi_przefiltrowane.csv',
            mime='text/csv',
        )
