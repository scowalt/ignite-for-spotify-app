module Ignite.Matching.StringNormalization

open System.Text.RegularExpressions

let private featuringRegex =
    Regex(@"\s*(ft\.?|feat\.?|featuring|\s&\s|\sand\s)\s*.*$", RegexOptions.Compiled ||| RegexOptions.IgnoreCase)

let private parentheticalRegex =
    Regex(@"\s*[\(\[\{].*?[\)\]\}]\s*", RegexOptions.Compiled)

let private contractions =
    [| ("I'm", "I am")
       ("you're", "you are")
       ("we're", "we are")
       ("they're", "they are")
       ("it's", "it is")
       ("that's", "that is")
       ("what's", "what is")
       ("who's", "who is")
       ("there's", "there is")
       ("here's", "here is")
       ("where's", "where is")
       ("don't", "do not")
       ("doesn't", "does not")
       ("didn't", "did not")
       ("won't", "will not")
       ("wouldn't", "would not")
       ("can't", "cannot")
       ("couldn't", "could not")
       ("shouldn't", "should not")
       ("isn't", "is not")
       ("aren't", "are not")
       ("wasn't", "was not")
       ("weren't", "were not")
       ("haven't", "have not")
       ("hasn't", "has not")
       ("hadn't", "had not")
       ("let's", "let us")
       ("I'll", "I will")
       ("you'll", "you will")
       ("we'll", "we will")
       ("they'll", "they will")
       ("I've", "I have")
       ("you've", "you have")
       ("we've", "we have")
       ("they've", "they have")
       ("I'd", "I would")
       ("you'd", "you would")
       ("we'd", "we would")
       ("they'd", "they would") |]

let private expansions =
    [| ("I am", "I'm")
       ("you are", "you're")
       ("we are", "we're")
       ("they are", "they're")
       ("it is", "it's")
       ("do not", "don't")
       ("does not", "doesn't")
       ("did not", "didn't")
       ("will not", "won't")
       ("cannot", "can't")
       ("is not", "isn't")
       ("are not", "aren't")
       ("have not", "haven't")
       ("has not", "hasn't") |]

let removeFeaturingArtists (artist: string) =
    featuringRegex.Replace(artist, "").Trim()

let removeParenthetical (text: string) =
    parentheticalRegex.Replace(text, "").Trim()

let expandContractions (text: string) =
    let mutable result = text

    for (contraction, expansion) in contractions do
        result <- Regex.Replace(result, $@"\b{Regex.Escape(contraction)}\b", expansion, RegexOptions.IgnoreCase)

    result

let contractExpansions (text: string) =
    let mutable result = text

    for (expansion, contraction) in expansions do
        result <- Regex.Replace(result, $@"\b{Regex.Escape(expansion)}\b", contraction, RegexOptions.IgnoreCase)

    result
