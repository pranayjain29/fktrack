# analytical_report.py
import matplotlib
matplotlib.use('Agg')
import io
from matplotlib.figure import Figure
import pandas as pd
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Image, Spacer, Table, TableStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
import seaborn as sns
from matplotlib.ticker import FuncFormatter
from wordcloud import WordCloud
from sklearn.cluster import KMeans


def generate_top_10_brands_graph_and_table(df, metric, story, aggre = 'sum'):
        
        total_metric = df[metric].sum()
        df = df.copy()
        df_grouped = df.groupby('Brand').agg({metric: aggre}).reset_index()

        df_grouped['Percentage Share'] = (df_grouped[metric] / total_metric * 100).round(1)

        top_10_brands = df_grouped.nlargest(10, metric)
        fig, ax = plt.subplots(figsize=(10, 6))

        palette = sns.color_palette("Blues", n_colors=len(top_10_brands))[::-1]
        sns.barplot(x=top_10_brands['Brand'], y=top_10_brands[metric], hue=top_10_brands['Brand'],
                    palette=palette, ax=ax, legend=False, width=0.7)
        
        # Set titles and labels
        ax.set_title(f'Top 10 Brands Based on {metric}', fontsize=16, fontweight='bold', fontname='serif')
        ax.set_xlabel('Brand', fontsize=14, fontname='serif', fontweight='bold')
        ax.set_ylabel(metric, fontsize=14, fontname='serif', fontweight='bold')
        ax.grid(False)


        for i, percentage in enumerate(top_10_brands['Percentage Share']):
            ax.text(i, top_10_brands[metric].iloc[i], f'{percentage:.1f}%', ha='center', va='bottom', fontsize=12, fontweight='bold')

        ax.set_xticks(range(len(top_10_brands['Brand'])))
        ax.set_xticklabels(ax.get_xticklabels(), ha='center', fontsize=12)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{int(x):,}'))  # Format y-axis with commas
        plt.tight_layout()

        # Save plot to a BytesIO buffer
        graph_buffer = io.BytesIO()
        plt.savefig(graph_buffer, format='png', bbox_inches='tight', pad_inches=0.1, dpi=300)
        graph_buffer.seek(0)
        plt.close(fig)

        print("Figure Done")
        # Add graph to the PDF
        story.append(Image(graph_buffer, width=400, height=240))
        story.append(Spacer(1, 0.3 * inch))  # Add space after graph

        top_10_brands_sorted = top_10_brands.sort_values(by=metric, ascending=False)
        data = [['Brand', f'Total {metric}', '% Share in Visibility']]
        data.extend(top_10_brands_sorted[['Brand', metric, 'Percentage Share']].values.tolist())
        table = Table(data)

        table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Times-Roman'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, (0, 0, 0)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))

        story.append(table)
        story.append(Spacer(1, 0.4 * inch))  # Add space after table

def generate_top_10_brands_graph(df, metric, story, aggre='mean', sortt = "Top"):
    df = df.copy()
    df_grouped = df.groupby('Brand').agg({metric: aggre}).reset_index()

    top_10_brands = []

    if sortt == "Top":
        top_10_brands = df_grouped.nlargest(10, metric)
    else:
        top_10_brands = df_grouped.nsmallest(10, metric)

    fig, ax = plt.subplots(figsize=(10, 6))

    palette = sns.color_palette("Blues", n_colors=len(top_10_brands))[::-1]
    sns.barplot(x=top_10_brands['Brand'], y=top_10_brands[metric], palette=palette, ax=ax, width=0.7)
    
    # Set titles and labels
    if sortt=="Top":
        ax.set_title(f'Top 10 Brands Based on {metric}', fontsize=16, fontweight='bold', fontname='serif')
    else:
        ax.set_title(f'Bottom 10 Brands Based on {metric}', fontsize=16, fontweight='bold', fontname='serif')
    ax.set_xlabel('Brand', fontsize=14, fontname='serif', fontweight='bold')
    ax.set_ylabel(f'Mean {metric}', fontsize=14, fontname='serif', fontweight='bold')
    ax.grid(False)

    # Add mean labels above each bar
    for i, mean_value in enumerate(top_10_brands[metric]):
        ax.text(i, mean_value, f'{mean_value:.1f}', ha='center', va='bottom', fontsize=12, fontweight='bold')

    ax.set_xticks(range(len(top_10_brands['Brand'])))
    ax.set_xticklabels(ax.get_xticklabels(), ha='center', fontsize=12)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{int(x):,}'))  # Format y-axis with commas
    plt.tight_layout()

    # Save plot to a BytesIO buffer
    graph_buffer = io.BytesIO()
    plt.savefig(graph_buffer, format='png', bbox_inches='tight', pad_inches=0.1, dpi=300)
    graph_buffer.seek(0)
    plt.close(fig)
    
    # Add graph to the PDF
    story.append(Image(graph_buffer, width=400, height=240))
    story.append(Spacer(1, 0.3 * inch)) 

    print(f"Figure Done for {sortt}")
    

def generate_histogram_plot(df, column_name, story, bins=10):

    # Create the plot
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.histplot(df[column_name], bins=bins, kde=True, color='skyblue', ax=ax)

    # Set titles and labels
    ax.set_title(f'Histogram of {column_name}', fontsize=16, fontweight='bold', fontname='serif')
    ax.set_xlabel(column_name, fontsize=14, fontweight='bold', fontname='serif')
    ax.set_ylabel('Frequency', fontsize=14, fontweight='bold', fontname='serif')
    ax.grid(False)

    # Apply tight layout
    plt.tight_layout()

    # Save plot to a BytesIO buffer
    graph_buffer = io.BytesIO()
    plt.savefig(graph_buffer, format='png', bbox_inches='tight', pad_inches=0.1, dpi=300)
    graph_buffer.seek(0)
    plt.close(fig)

    # Add the plot to the story
    story.append(Image(graph_buffer, width=400, height=240))
    story.append(Spacer(1, 0.4 * inch))  # Add space after the plot


def create_pdf_report(query, pages, df):

    df.loc[:, 'Count'] = 1
    df = df[df['Sponsored']=='No']
    # Custom style with Times New Roman font
    custom_style = ParagraphStyle(
        name='CustomStyle',
        fontName='Times-Roman',
        fontSize=12,
        leading=16,
        leftIndent=16
    )
    print("Custom Style Set")

    # Create a BytesIO buffer for the PDF
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
    story = []

    # Add title
    title = Paragraph(
        f"Flipkart Market Report for {query}",
        ParagraphStyle(
            name='Title',
            fontName='Times-Bold',
            fontSize=24,
            leading=48,
            alignment=TA_CENTER
            )
        )

    story.append(title)
    story.append(Spacer(1, 0.2 * inch))  # Add space after title

    # Add market size information with rupee symbol and bold
    total_revenue = df['Weekly Revenue'].sum() * 52.5

    df_grouped = df.groupby('Brand')['DRR'].sum().reset_index()
    df_grouped = df_grouped.sort_values(by='DRR', ascending=False)

    # Calculate the cumulative percentage of market control
    df_grouped['Cumulative Share'] = df_grouped['DRR'].cumsum() / df_grouped['DRR'].sum() * 100

    market_state = "None"

    if df_grouped['Cumulative Share'].iloc[0] >= 70:
        market_state = "Monopoly"
    elif df_grouped['Cumulative Share'].iloc[1] >= 70:
        market_state = "Duopoly"
    elif df_grouped['Cumulative Share'].iloc[4] >= 70:
        market_state = "Imperfect Competition"
    elif df_grouped['Cumulative Share'].iloc[6] >= 70:
        market_state = "Monopolistic Competition"
    else:
        market_state = "Perfect Competition"

    print(market_state)
    market_size_text = (
        f"Estimated total market size of <b>{query}</b> on Flipkart, considering {pages} pages, "
        f"is approximately <b>INR. {total_revenue:,.0f}</b> in annual revenue."
        f"The state of the market is: <b>{market_state}</b>."
    )

    print("Market Size Done")

    story.append(Paragraph(market_size_text, custom_style))
    story.append(Spacer(1, 0.2 * inch))  # Add space after market size text

    generate_top_10_brands_graph_and_table(df, 'Count', story)
    generate_top_10_brands_graph_and_table(df, 'Weekly Revenue', story)
    generate_top_10_brands_graph_and_table(df, 'DRR', story)
    generate_top_10_brands_graph(df,'Price',story)
    generate_top_10_brands_graph(df,'Price',story, sortt="Bottom")

    meann = df['Price'].mean()
    stdd = df['Price'].std()

    df_copy = df[(df['Price'] >= (meann - 2 * stdd)) & (df['Price'] <= (meann + 2 * stdd))]
    generate_histogram_plot(df_copy,'Price',story)
    generate_histogram_plot(df,'DRR',story)

    print("Table Done")


    kmeans = KMeans(n_clusters=2, random_state=0)
    df['Cluster'] = kmeans.fit_predict(df[['DRR']])

    for cluster in df['Cluster'].unique():
        cluster_df = df[df['Cluster'] == cluster]
        features_columns = [col for col in cluster_df.columns if col.startswith('feature')]
        
        # Combine title and features
        combined_title = cluster_df[['Title'] + features_columns].fillna('').apply(' '.join, axis=1)
        text1 = ' '.join(combined_title)

        print(f"Features for Cluster {cluster} ready!")

        # Calculate average DRR for the cluster
        avg_drr = cluster_df['DRR'].mean()

        # Add cluster title with average DRR to the story
        cluster_title1 = Paragraph(
            f"Word Cloud of Title for Cluster {cluster} (Average DRR: {avg_drr:.2f})",
            ParagraphStyle(name='ClusterTitle', fontName='Times-Bold', fontSize=16, leading=24)
        )

        # Generate word clouds
        wordcloud1 = WordCloud(width=800, height=400, background_color='white').generate(text1)

        # Save word clouds to BytesIO buffers
        wordcloud_buffer1 = io.BytesIO()
        wordcloud1.to_image().save(wordcloud_buffer1, format='PNG')
        wordcloud_buffer1.seek(0)

        print(f"Wordcloud for Cluster {cluster} saved")

        # Add the title and word clouds to the story
        story.append(cluster_title1)
        story.append(Spacer(1, 0.1 * inch))  # Add space before the word clouds
        story.append(Image(wordcloud_buffer1, width=400, height=200))
        story.append(Spacer(1, 0.4 * inch))  # Add space after the word clouds


    # Build the PDF
    doc.build(story)
    pdf_buffer.seek(0)
    print("PDF built successfully")

    return pdf_buffer
