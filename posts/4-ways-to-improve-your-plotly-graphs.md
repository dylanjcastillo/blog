---
title: "4 Ways To Improve Your Graphs Using Plotly"
aliases:
  - /4-ways-to-improve-your-plotly-graphs/
description-meta: "Making high-quality data visualizations is a critical skill for Data Scientists. Learn how to get better at it using Plotly's python library."
date: "05/25/2020"
date-modified: "2024-07-13"
toc: true
toc-depth: 3
lightbox: true
fig-cap-location: margin
categories:
  - python
  - dataviz
author:
  - name: Dylan Castillo
    url: https://dylancastillo.co
    affiliation: Iwana Labs
    affiliation-url: https://iwanalabs.com
citation: true
comments:
  utterances:
    repo: dylanjcastillo/blog_comments
    theme: dark-blue
    issue-term: pathname
---

These last weeks I've been working on an application using Dash and Plotly. These tools are great if you want to get something out quickly. But, as usual, there's no magical `make_beautiful_graphs` parameter you can set to `True` by default.

If you want to have beautiful and customized visualizations in your application, you'll need to spend some time playing around with Plotly's extensive list of figures' attributes. I wanted to have something better than the default looks, so I went through Plotly's documentation, old code snippets I had, and Stack Overflow questions.

This is not the first time I found myself doing that. However, this time I decided to keep track of the things I frequently do when making graphs with Plotly. That way, I wouldn't need to read the same documentation or browse the same Stack Overflow questions next time.

In this article I'm compiling a list of things I frequently do when building data visualizations using Plotly. Rest assured, [I've been working in data-related positions for a while](https://dylancastillo.co/about/), so you will not find outrageous things like _how to make 3D pie charts_. These improvements are based on a sample of one, but I've frequently seen others applying similar ideas.

I'm focusing on practical and simple improvements that apply to most of the basic charts: scatter plots, line charts, bar charts, and some statistical charts. Here you will find things like _removing gridlines_ and not things like _selecting the best colors for your 4D contour plot_.

First, I'll do a brief introduction on how you build graphs using Plotly. Next, I'll provide a list of improvements and the reasoning behind them. Last, I'll give additional recommendations I've found useful when working with Plotly and other plotting libraries.

## How to Make a Graph Using Plotly

There are three things you need to know about the inner workings of Plotly:

First, making a graph in Plotly is essentially populating a Python dictionary. This dictionary is usually referred to as _figure_.

Second, there are two keys in the _figure_ dictionary: _layout_ and _data._ In _layout,_ you define the looks of your graph like the typography, titles, and axes. In the _data_ key, you set the values and information of the traces you'll be plotting. That could be something like [1, 2, 3] for X, [5, 3, 9] for Y and bar chart type.

Finally, once you populate the _figure_ dictionary, it is serialized (transformed) into a JSON structure. This resulting data structure is then used by the Plotly JavaScript library to plot your chart.

That's it.

So, how do you make a _figure_?

There are multiple ways to do it. The lowest-level approach is to use Python dictionaries, and the highest-level one is using the _Plotly Express_ interface*.* I tend to use a mid-level interface called _Figure Constructor_. It's easier to debug than using Python dictionaries, and it's more flexible than _Plotly Express_.

The code for making a graph using the _Figure Constructor_ looks as follows:

```python
import plotly.graph_objects as go
import numpy as np
np.random.seed(42)

# Simulate data
returns = np.random.normal(0.01, 0.2, 100)
price = 100 * np.exp(returns.cumsum())
time = np.arange(100)

# Generate graph using Figure Constructor
layout = go.Layout(
    title="Historic Prices",
    xaxis_title="time",
    yaxis_title="price"
)

fig = go.Figure(
    data=go.Scatter(x=time, y=price),
    layout=layout
)
fig.show()
```

How to make make a line chart using Plotly

This is the resulting graph:

<iframe class="plotly-graph" src="https://chart-studio.plotly.com/~dylanjcastillo/658.embed?autosize=true&link=false"></iframe>
<figcaption>Basic plot in Plotly</figcaption>

For the code snippets listed below, I used the _Figure Constructor_ approach. You may need to adjust the code to make it work for your case if you are using a different interface.

So let's get down to the meat and potatoes.

## List of Improvements

Here's the list of things I usually do to improve Plotly graphs:

- #1: Remove gridlines and background color
- #2: Keep consistent colors across graphs
- #3: Use spikelines to compare data points
- #4: Remove floating menu, disable zoom and adjust click behavior

### #1: Remove gridlines and background color

Gridlines are lines that cross the chart to show axis divisions. They help the viewer visualize the value represented by an unlabeled data point fast. However, gridlines are not very useful when working with interactive graphs. You can hover over a data point and see its value. So more often than not, I remove gridlines when working with Plotly.

Here's how you can do it:

```python
import plotly.graph_objects as go
import numpy as np
np.random.seed(42)

# Simulate data
returns = np.random.normal(0.01, 0.2, 100)
price = 100 * np.exp(returns.cumsum())
time = np.arange(100)

layout = go.Layout(
    title="Historic Prices",
    plot_bgcolor="#FFF",  # Sets background color to white
    xaxis=dict(
        title="time",
        linecolor="#BCCCDC",  # Sets color of X-axis line
        showgrid=False  # Removes X-axis grid lines
    ),
    yaxis=dict(
        title="price",
        linecolor="#BCCCDC",  # Sets color of Y-axis line
        showgrid=False,  # Removes Y-axis grid lines
    )
)

fig = go.Figure(
    data=go.Scatter(x=time, y=price),
    layout=layout
)
fig.show()
```

Code snippet to remove grid lines

And this is how it looks:

<iframe class="plotly-graph" src="https://chart-studio.plotly.com/~dylanjcastillo/627.embed?autosize=true&link=false"></iframe>
<figcaption>Line chart without gridlines</figcaption>

### #2: Keep consistent colors across graphs

When working with categories, there are two things people usually like to do. First, they want to assign some specific colors to each group. For instance, if you are analyzing electoral results in the US, you probably want to use particular blue and red variations to identify the Democratic and Republican parties.

Second, you want this color to remain consistent across all the graphs you do. For example, if you are analyzing some real-world companies, you may want to use their distinctive colors to plot their prices but also when you analyze their returns.

Here's how you can do that using Plotly:

```python
import plotly.graph_objects as go
import numpy as np
np.random.seed(42)

# Simulate data
returns_A = np.random.normal(0.01, 0.2, 100)
returns_B = np.random.normal(0.01, 0.2, 100)
returns = np.append(returns_A, returns_B)

prices_A = 100 * np.exp(returns_A.cumsum())
prices_B = 100 * np.exp(returns_B.cumsum())
prices = np.append(prices_A, prices_B)

companies = ["A"] * 100 + ["B"] * 100
time = np.append(np.arange(100), np.arange(100))

df = pd.DataFrame({
    "company": companies,
    "time": time,
    "price": prices,
    "returns": returns
})

# Build graph
COLORS_MAPPER = {
    "A": "#38BEC9",
    "B": "#D64545"
}

layout = go.Layout(
    title="Performance of A vs. B",
    plot_bgcolor="#FFFFFF",
    barmode="stack",
    xaxis=dict(
        domain=[0, 0.5],
        title="time",
        linecolor="#BCCCDC",
    ),
    yaxis=dict(
        title="price",
        linecolor="#BCCCDC"
    ),
    xaxis2=dict(
        domain=[0.6, 1],
        title="returns",
        linecolor="#BCCCDC",
    ),
    yaxis2=dict(
        anchor="x2",
        linecolor="#BCCCDC"
    )
)

data = []
for company,col in COLORS_MAPPER.items():
    time = df.loc[df.company == company, "time"]
    price = df.loc[df.company == company, "price"]
    returns = df.loc[df.company == company, "returns"]
    line_chart = go.Scatter(
        x=time,
        y=price,
        marker_color=col,  # Defines specific color for a trace
        legendgroup=company,  # Groups traces belonging to the same group in the legend
        name=company
    )
    histogram = go.Histogram(
        x=returns,
        marker_color=col,  # Defines specific color for a trace
        legendgroup=company,  # Groups traces belonging to the same group in the legend
        xaxis="x2",
        yaxis="y2",
        showlegend=False
    )
    data.append(line_chart)
    data.append(histogram)

fig = go.Figure(data=data, layout=layout)
fig.show()
```

<iframe class="plotly-graph" src="https://chart-studio.plotly.com/~dylanjcastillo/671.embed?autosize=true&link=false"></iframe>
<figcaption>Consistent colors across graphs</figcaption>

The snippet above allows you to keep consistent colors when working with multiple graphs that share the same categories. The critical part is the `COLOR_MAPPER` dictionary and its use when adding new traces. This dictionary is the mapping of the categories and colors you'll be using across your charts.

Whenever you add a trace to a graph, you can assign the right color to the `marker_color` attribute by getting it from the `COLOR_MAPPER` dictionary.

The resulting graph looks as follows:

Consistent colors across graphs

### #3: Use spike lines to compare data points

A spike line is a vertical or horizontal line that appears when hovering on data. It's useful for comparing values in line charts and scatter plots. This is how you can add those using Plotly:

```python
import plotly.graph_objects as go
import numpy as np
np.random.seed(42)

# Simulate data
returns_A = np.random.normal(0.01, 0.2, 100)
returns_B = np.random.normal(0.01, 0.2, 100)
returns = np.append(returns_A, returns_B)

prices_A = 100 * np.exp(returns_A.cumsum())
prices_B = 100 * np.exp(returns_B.cumsum())
prices = np.append(prices_A, prices_B)

companies = ["A"] * 100 + ["B"] * 100
time = np.append(np.arange(100), np.arange(100))

df = pd.DataFrame({
    "company": companies,
    "time": time,
    "price": prices,
    "returns": returns
})

# Build graph
layout = go.Layout(
    title="Performance of A vs. B",
    plot_bgcolor="#FFFFFF",
    hovermode="x",
    hoverdistance=100, # Distance to show hover label of data point
    spikedistance=1000, # Distance to show spike
    xaxis=dict(
        title="time",
        linecolor="#BCCCDC",
        showspikes=True, # Show spike line for X-axis
        # Format spike
        spikethickness=2,
        spikedash="dot",
        spikecolor="#999999",
        spikemode="across",
    ),
    yaxis=dict(
        title="price",
        linecolor="#BCCCDC"
    )
)

data = []
for company in ["A", "B"]:
    time = df.loc[df.company == company, "time"]
    price = df.loc[df.company == company, "price"]
    returns = df.loc[df.company == company, "returns"]
    line_chart = go.Scatter(
        x=time,
        y=price,
        name=company
    )
    data.append(line_chart)

fig = go.Figure(data=data, layout=layout)
fig.show()
```

Code snippet to add spike lines to chart

This is the resulting graph:

<iframe class="plotly-graph" src="https://chart-studio.plotly.com/~dylanjcastillo/700.embed?autosize=true&link=false"></iframe>
<figcaption>Chart with spike lines</figcaption>

### #4: Remove floating menu, disable zoom and adjust click behavior

I'm not too fond of the floating menu that Plotly adds to your chart by default. It makes graphs look _cool_, but I've rarely seen people using it. It has so many options that it's just confusing for someone looking at a graph for the first time. Usually, I remove it.

Also, I like to re-define two other user interaction parameters. I prefer to limit the users' ability to zoom in and change the behavior of clicking on a trace in the legend. In Plotly, by default, if you want to inspect a trace on its own, you have to double-click on the trace, instead of just clicking on it. That's not very intuitive, so I tend to invert that behavior.

This is how you can apply those changes:

```python
import plotly.graph_objects as go
import numpy as np
np.random.seed(42)

# Simulate data
returns_A = np.random.normal(0.01, 0.2, 100)
returns_B = np.random.normal(0.01, 0.2, 100)
returns = np.append(returns_A, returns_B)

prices_A = 100 * np.exp(returns_A.cumsum())
prices_B = 100 * np.exp(returns_B.cumsum())
prices = np.append(prices_A, prices_B)

companies = ["A"] * 100 + ["B"] * 100
time = np.append(np.arange(100), np.arange(100))

df = pd.DataFrame({
    "company": companies,
    "time": time,
    "price": prices,
    "returns": returns
})

# Build graph
layout = go.Layout(
    title="Performance of A vs. B",
    plot_bgcolor="#FFFFFF",
    legend=dict(
        # Adjust click behavior
        itemclick="toggleothers",
        itemdoubleclick="toggle",
    ),
    xaxis=dict(
        title="time",
        linecolor="#BCCCDC",
        fixedrange=True
    ),
    yaxis=dict(
        title="price",
        linecolor="#BCCCDC",
        fixedrange=True
    )
)

data = []
for company in ["A", "B"]:
    time = df.loc[df.company == company, "time"]
    price = df.loc[df.company == company, "price"]
    returns = df.loc[df.company == company, "returns"]
    line_chart = go.Scatter(
        x=time,
        y=price,
        name=company
    )
    data.append(line_chart)

fig = go.Figure(data=data, layout=layout)
fig.show(config={"displayModeBar": False, "showTips": False}) # Remove floating menu and unnecesary dialog box
```

This is the resulting graph:

<iframe class="plotly-graph" src="https://chart-studio.plotly.com/~dylanjcastillo/716.embed?autosize=true&link=false&modebar=false"></iframe>
<figcaption>Chart without floating menu, no-zoom and adjusted click behavior</figcaption>

## Additional recommendations

There are three things that I've found useful for learning how to make better data visualizations:

1. Get feedback from your audience: This is not always possible. But if you can do it, always prioritize getting input from those who will use your data visualizations. If you are working on a dashboard, the first thing you should do is understand what problem your dashboard solves. Then see users interacting with it. That has the highest ROI for your time.
2. Check out [Storytelling with Data by Cole Knaflic](http://www.storytellingwithdata.com/): It's a great book if you want to level-up your data visualization design skills. It provides a lot of practical advice and compelling use cases.
3. [Plotly's Figure Reference](https://plotly.com/python/reference/): Get used to Plotly's Figure Reference and documentation. You'll be using it a lot. Though, there's nothing to worry about. Plotly has great documentation!

## Closing Words

I hope you've find these ideas useful. There might be some things that do not resonate with you, or others that you feel are missing. If that's the case, please let me know in the comments below. I'll be happy to update this and add other valuable advice.

If you want to keep up-to-date with what I'm doing you can follow me on [twitter](https://twitter.com/dylanjcastillo).
