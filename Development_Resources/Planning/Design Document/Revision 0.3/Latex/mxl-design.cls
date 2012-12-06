% This document provides the tech memo class for use on Michigan
% Exploration Laboratory documents
%
% Author: K. Scott Tripp

%***** Template version log *****************************************
% 20 July 2012		- Initial draft (copied from mxl-memo)	- KST
% 30 July 2012		- Initial release                      	- KST
% 1 August 2012		- Added hyperref and signature command 	- KST
% 12 November 2012	- Added line break between paragraphs 	- KST
%********************************************************************
\newcommand{\templateRev}{1.2}
\newcommand{\revDate}{12 July 2012}

% Class Definition
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{mxl-design}[2012/02/30 - A design document class for MXL]


% Based off the Article class
\LoadClassWithOptions{article}

% Package requirements
\usepackage{fullpage}
\usepackage{graphicx}
\usepackage{fancyhdr}
\usepackage{etoolbox}
\usepackage{array}
\usepackage{hyperref}
\usepackage{parskip}
\RequirePackage{ifthen}

\hypersetup{
colorlinks,
linkcolor=blue,
citecolor=ForestGreen,
urlcolor=magenta
}
\setlength\parindent{0pt}

% Design Doc commands
\renewcommand{\author}[1]{\gdef\@author{#1}}
\def\@author{\relax}

\renewcommand{\title}[1]{\gdef\@title{#1}}
\def\@title{\relax}

\newcommand{\docnum}[1]{\gdef\@docnum{#1}}
\def\@docnum{\relax}

% Signature Command
\newcommand{\namesigdate}[2][2.75in]{%
  \begin{tabular}{@{}p{#1}@{}}
    #2 \\[2\normalbaselineskip] \hrule \\[0pt]
    {\small \textit{Signature}} \\[2\normalbaselineskip] \hrule \\[0pt]
    {\small \textit{Date}}
  \end{tabular}
}


%== This section needs to be debugged to make a better controlled version tbable
%\newcommand{\revList}[1]{}
%\newcommand{\dateList}[1]{}
%\newcommand{\noteList}[1]{}
%\newcommand{\initList}[1]{}
%\newcommand{\PlaceHolder}[1]{}
%
%\newcommand{\version}[4]{
%	\gdef\@revision{#1}
%	\gdef\@revdate{#2}
%	\gdef\@comment{#3}
%	\gdef\@initials{#4}
%}
%%\gdef\@PlaceHolder{\revList, \@revision}
%\renewcommand{\PlaceHolder}[1]{\revList, \@revision}
%\renewcommand{\revList}[1]{\PlaceHolder}
%%\gdef\@revList{OINK}
%%\gdef\@revList{\@revList, \@revision}

%\renewcommand{\dateList}[1]{\@dateList, \@revdate}
%\renewcommand{\noteList}[1]{\@noteList, \@comment}
%\renewcommand{\initList}[1]{\@initList, \@initials}

%**** Revision History table ****************************************
% Version{number}{date}{Commend}{Author}
%\newcommand{\changelog}{}
%\@for\revHist:=\revList\do{%
%	\g@addto@macro\changelog{%
%		\@revision & \@revdate & \@comment \@initials\\\hline}
%}

% Geometry variables
\newcommand{\TableUnindent}{-0.2cm}

%===Document formatting==============================================

% Title block
\renewcommand{\maketitle}{\makeTitleBlock}
\newcommand\makeTitleBlock{

% Geometry definitions
\newcommand{\blockWidth}{0.79\textwidth}

%\newcommand{\HRule}{\rule{1.4\textwidth}{0.5mm}}
\newcommand{\HRule}{\rule{1.0\textwidth}{0.5mm}}

%**** Banner and Title Block****************
\begin{flushleft}
\begin{minipage}{\blockWidth}	% outer box
\begin{minipage}[t]{0.78\textwidth}	% banner
	%\raisebox{0.5in}{\Huge \sc MXL Tech Memo}
	{\LARGE \@title}\\ 
	\HRule \\
	{\small Document \@docnum}\\[0.1in]
\end{minipage}
\begin{minipage}[b]{0.78\textwidth}	% title block
	\begin{tabular}{l l}
		\hspace{\TableUnindent}{\bf Authors:} &{\@author \par}\\[0.05in]
		\hspace{\TableUnindent}{\bf Date:} &{\today}\\[0.05in]
	\end{tabular}
\end{minipage}
\end{minipage}
\begin{minipage}{0.2\textwidth}
	\begin{flushright}
	\includegraphics[width=1.2in]{Dish-Logo-4.jpg}
	\end{flushright}
\end{minipage}
\end{flushleft}

% Revision history table
%\begin{tabular}{|l|l|l|l|}
%	\hline
%	Rev & Date & Notes & Authors \\ 
%	\hline \hline
%	\changelog
%\end{tabular}
}

%**** Define page headers. ******************************************

\renewcommand{\footrulewidth}{0.4pt}% default is 0pt

% First page

\fancypagestyle{firstPage}
{
	\fancyhf{}
	\renewcommand{\headrulewidth}{0pt}% default is 0.4pt
	\renewcommand{\headheight}{0pt}% 
	\renewcommand{\topmargin}{-25pt}% 
	\fancyfoot[L]{Template version \templateRev}
	\fancyfoot[C]{MXL Tech Memo}
	\fancyfoot[R]{Page \thepage}
}

\thispagestyle{firstPage}
%\fancyhf{}
%
%\lfoot{\today}
%\cfoot{MXL Tech Memo}
%\rfoot{Template version \templateRev}

% Remaining pages
\fancyhf{}
\pagestyle{fancy}
\headsep 25pt

\lhead{\@title}
\chead{Document \@docnum}
\rhead{\today}

\lfoot{Template version \templateRev}
\cfoot{MXL Tech Memo}
\rfoot{Page \thepage}
