/**
 * GPFinder - Frontend search and results.
 */
(function () {
  const searchForm = document.getElementById("searchForm");
  const searchInput = document.getElementById("searchInput");
  const searchBtn = document.getElementById("searchBtn");
  const resultsSection = document.getElementById("resultsSection");
  const resultsPlaceholder = document.getElementById("resultsPlaceholder");
  const resultsTitle = document.getElementById("resultsTitle");
  const resultsMeta = document.getElementById("resultsMeta");
  const resultsError = document.getElementById("resultsError");
  const resultsLoading = document.getElementById("resultsLoading");
  const resultsList = document.getElementById("resultsList");
  const resultsEmpty = document.getElementById("resultsEmpty");
  const resultsEmptyText = resultsEmpty ? resultsEmpty.querySelector("p") : null;
  const sortSelect = document.getElementById("sortSelect");
  const scopeToggle = document.getElementById("scopeToggle");
  const voiceSearchBtn = document.getElementById("voiceSearchBtn");
  const voiceStatus = document.getElementById("voiceStatus");
  const speakResultsBtn = document.getElementById("speakResultsBtn");
  const stopSpeakBtn = document.getElementById("stopSpeakBtn");
  const languageSelect = document.getElementById("languageSelect");
  const qualityHelpBtn = document.getElementById("qualityHelpBtn");
  const qualityHelpText = document.getElementById("qualityHelpText");
  const qualityPanel = document.querySelector(".quality-panel");
  const SCOPE_STORAGE_KEY = "gpfinder-search-scope";
  const LANGUAGE_STORAGE_KEY = "gpfinder-language";
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let isListening = false;
  let latestResponse = { results: [], query: "" };
  /** Monotonic id so stale fetch responses cannot leave the loading UI stuck on. */
  let searchSeq = 0;
  const I18N = {
    en: {
      resultsTitle: "Results",
      found: "found for",
      scopeAll: "including broader services",
      scopeCore: "GP practices only",
      noResults: "No practices found for your search. Try a different postcode or town.",
      likelyServices: "Likely services",
      useful: "Useful",
      rateThis: "Rate this result:",
      incorrect: "Report details",
      readTop: "Read top results",
      stopReading: "Stop reading",
      searchHint: "Enter a postcode to find GPs by distance, or search by town name",
      listening: "Listening... say a postcode or town name.",
      searchingFor: "Searching for:",
      voiceError: "Voice input was not understood. Please try again.",
      unsupportedVoice: "Voice search is not supported in this browser.",
      feedbackThanks: "Thanks for your feedback.",
      feedbackPrompt: "Please describe what is incorrect.",
    },
    hi: {
      resultsTitle: "परिणाम",
      found: "के लिए मिले",
      scopeAll: "विस्तृत सेवाओं सहित",
      scopeCore: "केवल जीपी प्रैक्टिस",
      noResults: "कोई परिणाम नहीं मिला। कृपया दूसरा पोस्टकोड या शहर खोजें।",
      likelyServices: "संभावित सेवाएं",
      useful: "उपयोगी",
      rateThis: "इस परिणाम को रेट करें:",
      incorrect: "विवरण रिपोर्ट करें",
      readTop: "शीर्ष परिणाम सुनें",
      stopReading: "पढ़ना बंद करें",
      searchHint: "दूरी के अनुसार जीपी खोजने के लिए पोस्टकोड दर्ज करें, या शहर से खोजें",
      listening: "सुन रहा है... पोस्टकोड या शहर बोलें।",
      searchingFor: "इसके लिए खोज रहा है:",
      voiceError: "आवाज़ समझ नहीं आई। कृपया फिर कोशिश करें।",
      unsupportedVoice: "इस ब्राउज़र में वॉइस सर्च उपलब्ध नहीं है।",
      feedbackThanks: "प्रतिक्रिया के लिए धन्यवाद।",
      feedbackPrompt: "कृपया बताएं क्या गलत है।",
    },
    zh: {
      resultsTitle: "结果",
      found: "的搜索结果",
      scopeAll: "包含更多基层医疗服务",
      scopeCore: "仅全科诊所",
      noResults: "未找到结果，请尝试其他邮编或城市。",
      likelyServices: "可能提供的服务",
      useful: "有帮助",
      rateThis: "为此结果评分：",
      incorrect: "报告信息错误",
      readTop: "朗读前几条结果",
      stopReading: "停止朗读",
      searchHint: "输入邮编按距离查找，或输入城市名称搜索",
      listening: "正在聆听，请说出邮编或城市。",
      searchingFor: "正在搜索：",
      voiceError: "未能识别语音，请重试。",
      unsupportedVoice: "当前浏览器不支持语音搜索。",
      feedbackThanks: "感谢您的反馈。",
      feedbackPrompt: "请描述错误信息。",
    },
    es: {
      resultsTitle: "Resultados",
      found: "encontrados para",
      scopeAll: "incluyendo servicios ampliados",
      scopeCore: "solo consultas de GP",
      noResults: "No se encontraron resultados. Prueba con otro código postal o ciudad.",
      likelyServices: "Servicios probables",
      useful: "Útil",
      rateThis: "Valora este resultado:",
      incorrect: "Reportar detalles",
      readTop: "Leer resultados principales",
      stopReading: "Dejar de leer",
      searchHint: "Introduce un código postal para buscar por distancia o una ciudad",
      listening: "Escuchando... diga un código postal o ciudad.",
      searchingFor: "Buscando:",
      voiceError: "No se entendió la voz. Inténtalo de nuevo.",
      unsupportedVoice: "La búsqueda por voz no está disponible en este navegador.",
      feedbackThanks: "Gracias por tus comentarios.",
      feedbackPrompt: "Describe qué detalle es incorrecto.",
    },
    ar: {
      resultsTitle: "النتائج",
      found: "نتيجة للبحث عن",
      scopeAll: "بما في ذلك خدمات الرعاية الموسعة",
      scopeCore: "عيادات GP فقط",
      noResults: "لم يتم العثور على نتائج. جرّب رمزًا بريديًا أو مدينة أخرى.",
      likelyServices: "الخدمات المحتملة",
      useful: "مفيد",
      rateThis: "قيّم هذه النتيجة:",
      incorrect: "الإبلاغ عن خطأ",
      readTop: "قراءة أفضل النتائج",
      stopReading: "إيقاف القراءة",
      searchHint: "أدخل الرمز البريدي للبحث حسب المسافة أو ابحث باسم المدينة",
      listening: "جاري الاستماع... قل الرمز البريدي أو المدينة.",
      searchingFor: "جارٍ البحث عن:",
      voiceError: "لم يتم فهم الصوت. حاول مرة أخرى.",
      unsupportedVoice: "البحث الصوتي غير مدعوم في هذا المتصفح.",
      feedbackThanks: "شكرًا لملاحظاتك.",
      feedbackPrompt: "يرجى وصف ما هو غير صحيح.",
    },
    fr: {
      resultsTitle: "Résultats",
      found: "trouvés pour",
      scopeAll: "incluant des services élargis",
      scopeCore: "cabinets GP uniquement",
      noResults: "Aucun résultat trouvé. Essayez un autre code postal ou une autre ville.",
      likelyServices: "Services probables",
      useful: "Utile",
      rateThis: "Notez ce résultat :",
      incorrect: "Signaler un détail",
      readTop: "Lire les meilleurs résultats",
      stopReading: "Arrêter la lecture",
      searchHint: "Saisissez un code postal pour la distance, ou une ville pour rechercher",
      listening: "Écoute... dites un code postal ou une ville.",
      searchingFor: "Recherche de :",
      voiceError: "La voix n'a pas été comprise. Réessayez.",
      unsupportedVoice: "La recherche vocale n'est pas prise en charge par ce navigateur.",
      feedbackThanks: "Merci pour votre retour.",
      feedbackPrompt: "Décrivez le détail incorrect.",
    },
  };
  const SPEECH_LANG = { en: "en-GB", hi: "hi-IN", zh: "zh-CN", es: "es-ES", ar: "ar-SA", fr: "fr-FR" };

  function setLoading(loading) {
    resultsLoading.hidden = !loading;
    searchBtn.disabled = loading;
    if (loading) {
      resultsError.hidden = true;
      resultsList.innerHTML = "";
      resultsEmpty.hidden = true;
    }
  }

  function showError(message) {
    resultsError.textContent = message;
    resultsError.hidden = false;
    resultsList.innerHTML = "";
    resultsEmpty.hidden = true;
  }

  function hideError() {
    resultsError.hidden = true;
  }

  function applyStarRatingVisual(starWrap, ratingValue) {
    if (!starWrap || ratingValue == null || isNaN(ratingValue)) return;
    var buttons = starWrap.querySelectorAll(".star-btn");
    buttons.forEach(function (btn) {
      var value = Number(btn.getAttribute("data-rate"));
      btn.classList.toggle("selected", value <= ratingValue);
    });
  }

  function clearStarRatingVisual(starWrap) {
    if (!starWrap) return;
    starWrap.querySelectorAll(".star-btn").forEach(function (btn) {
      btn.classList.remove("selected");
    });
  }

  function escapeHtml(s) {
    if (s == null || s === "") return "";
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function currentLanguage() {
    var lang = languageSelect ? languageSelect.value : "en";
    return I18N[lang] ? lang : "en";
  }

  function t(key) {
    var lang = currentLanguage();
    return (I18N[lang] && I18N[lang][key]) || I18N.en[key] || key;
  }

  function formatRating(rating, count) {
    if (rating == null) return "";
    const r = Number(rating);
    const c = count != null ? Number(count) : 0;
    if (isNaN(r)) return "";
    var str = r.toFixed(1) + " out of 5";
    if (c > 0) str += " (" + c + " reviews)";
    return str;
  }

  function mapsUrl(address, postcode) {
    var q = [address, postcode].filter(Boolean).join(", ");
    return "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(q);
  }

  function buildCard(practice) {
    var name = practice.name || "Unknown practice";
    var nameEsc = escapeHtml(name);
    var address = practice.address || "";
    var addressEsc = escapeHtml(address);
    var postcode = practice.postcode || "";
    var postcodeEsc = escapeHtml(postcode);
    var telephone = practice.telephone ? escapeHtml(practice.telephone) : "";
    var website = (practice.website || "").trim();
    var ratingStr = formatRating(practice.rating, practice.rating_count);
    var distance = practice.distance_miles;
    var relevance = practice.score;
    var serviceType = practice.service_type || "";
    var services = Array.isArray(practice.services) ? practice.services : [];
    var patientInfo = practice.patient_info || "";
    var orgCode = practice.organisation_code || practice.id || "";

    var nameBlock = nameEsc;
    if (website) {
      nameBlock = '<a href="' + escapeHtml(website) + '" target="_blank" rel="noopener noreferrer" class="practice-name-link">' + nameEsc + '</a>';
    }

    var addressBlock = "";
    if (address || postcode) {
      var mapHref = mapsUrl(address, postcode);
      addressBlock = '<a href="' + escapeHtml(mapHref) + '" target="_blank" rel="noopener noreferrer" class="practice-address-link">' +
        (addressEsc ? '<span class="practice-address">' + addressEsc + "</span>" : "") +
        (postcodeEsc ? '<span class="practice-postcode">' + postcodeEsc + "</span>" : "") +
        "</a>";
    }

    var distanceBadge = "";
    if (distance != null && typeof distance === "number") {
      distanceBadge = '<span class="practice-distance">' + escapeHtml(distance === 0 ? "<0.5 mi" : distance + " mi away") + "</span>";
    }
    var relevanceBadge = "";
    if (relevance != null && typeof relevance === "number") {
      relevanceBadge = '<span class="practice-relevance">Relevance ' + escapeHtml(relevance.toFixed(2)) + "</span>";
    }
    var typeBadge = "";
    if (serviceType) {
      typeBadge = '<span class="practice-type">' + escapeHtml(serviceType) + "</span>";
    }

    var metaParts = [];
    if (telephone) {
      metaParts.push('<span class="practice-meta-item">Tel: <a href="tel:' + escapeHtml(telephone.replace(/\s/g, "")) + '">' + telephone + "</a></span>");
    }
    if (ratingStr) {
      metaParts.push('<span class="practice-rating">' + escapeHtml(ratingStr) + "</span>");
    }
    if (orgCode) {
      metaParts.push('<span class="practice-meta-item">Org code: ' + escapeHtml(orgCode) + "</span>");
    }

    var metaHtml = metaParts.length ? '<div class="practice-meta">' + metaParts.join("") + "</div>" : "";

    var actions = "";
    if (website) {
      actions = '<a href="' + escapeHtml(website) + '" target="_blank" rel="noopener noreferrer" class="btn btn-primary">Visit practice website</a>';
    }
    if (address || postcode) {
      var dirUrl = mapsUrl(address, postcode);
      actions += '<a href="' + escapeHtml(dirUrl) + '" target="_blank" rel="noopener noreferrer" class="btn btn-secondary">Get directions</a>';
    }
    actions += '<button type="button" class="btn btn-secondary card-read-btn" data-read-name="' + nameEsc + '" data-read-town="' + escapeHtml(practice.town || "") + '" data-read-phone="' + telephone + '">Listen</button>';
    if (actions) {
      actions = '<div class="practice-actions">' + actions + "</div>";
    }

    var servicesHtml = "";
    if (services.length) {
      servicesHtml =
        '<div class="practice-services"><p class="practice-services-title">' + escapeHtml(t("likelyServices")) + '</p><ul class="practice-services-list">' +
        services.map(function (service) { return "<li>" + escapeHtml(service) + "</li>"; }).join("") +
        "</ul></div>";
    }

    var patientInfoHtml = patientInfo ? '<p class="practice-patient-info">' + escapeHtml(patientInfo) + "</p>" : "";
    var openingInfo = practice.opening_info || {};
    var openingHtml = "";
    if (openingInfo.status_label || openingInfo.next_opening || openingInfo.urgent_alternative) {
      openingHtml =
        '<div class="practice-opening">' +
        '<span class="practice-opening-status ' + (openingInfo.is_open_now ? "open" : "closed") + '">' + escapeHtml(openingInfo.status_label || "") + "</span>" +
        (openingInfo.next_opening ? '<span class="practice-opening-next">' + escapeHtml(openingInfo.next_opening) + "</span>" : "") +
        (openingInfo.urgent_alternative ? '<p class="practice-opening-urgent">' + escapeHtml(openingInfo.urgent_alternative) + "</p>" : "") +
        "</div>";
    }
    var appointmentInfo = practice.appointment_info || {};
    var appointmentHtml =
      '<div class="practice-appointment">' +
      (appointmentInfo.how_to_register ? '<p><strong>How to register:</strong> ' + escapeHtml(appointmentInfo.how_to_register) + "</p>" : "") +
      (appointmentInfo.urgent_booking ? '<p><strong>Urgent same-day:</strong> ' + escapeHtml(appointmentInfo.urgent_booking) + "</p>" : "") +
      ('<p><strong>Online consultation:</strong> ' + (appointmentInfo.online_consultation_available ? "Available" : "Check with provider") + "</p>") +
      "</div>";
    var travel = practice.travel_options || {};
    var travelHtml = "";
    var travelKeys = ["driving", "transit", "walking"];
    var travelItems = travelKeys
      .map(function (k) {
        var option = travel[k];
        if (!option || !option.url) return "";
        var label = option.label || k;
        var eta = option.eta ? " " + option.eta : "";
        return '<a class="travel-chip" href="' + escapeHtml(option.url) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(label + eta) + "</a>";
      })
      .filter(Boolean)
      .join("");
    if (travelItems) {
      travelHtml = '<div class="practice-travel"><p class="practice-services-title">Travel options</p><div class="travel-chips">' + travelItems + "</div></div>";
    }

    var starsHtml = '<div class="rating-wrap"><span class="rating-label">' + escapeHtml(t("rateThis")) + '</span><div class="star-rating" role="group" aria-label="Rate this result">';
    for (var i = 1; i <= 5; i += 1) {
      starsHtml += '<button type="button" class="star-btn" data-rate="' + i + '" data-feedback-practice-id="' + escapeHtml(practice.id || "") + '" data-feedback-practice-name="' + nameEsc + '" aria-label="Rate ' + i + ' star' + (i === 1 ? '' : 's') + '">★</button>';
    }
    starsHtml += "</div></div>";

    return (
      '<article class="practice-card">' +
      ((distanceBadge || relevanceBadge || typeBadge) ? '<div class="practice-card-header">' + distanceBadge + relevanceBadge + typeBadge + "</div>" : "") +
      '<h3 class="practice-name">' + nameBlock + "</h3>" +
      (addressBlock ? '<div class="practice-address-wrap">' + addressBlock + "</div>" : "") +
      metaHtml +
      openingHtml +
      servicesHtml +
      appointmentHtml +
      travelHtml +
      patientInfoHtml +
      actions +
      '<div class="practice-feedback-row">' +
      starsHtml +
      '<button type="button" class="mini-btn feedback-incorrect" data-feedback-type="incorrect" data-feedback-practice-id="' + escapeHtml(practice.id || "") + '" data-feedback-practice-name="' + nameEsc + '">' + escapeHtml(t("incorrect")) + "</button>" +
      '<span class="rating-confirmation" aria-live="polite"></span>' +
      "</div>" +
      "</article>"
    );
  }

  function sortResults(results, mode) {
    var copy = results.slice();
    if (mode === "distance") {
      copy.sort(function (a, b) {
        var da = typeof a.distance_miles === "number" ? a.distance_miles : Number.POSITIVE_INFINITY;
        var db = typeof b.distance_miles === "number" ? b.distance_miles : Number.POSITIVE_INFINITY;
        return da - db;
      });
      return copy;
    }
    if (mode === "name") {
      copy.sort(function (a, b) { return (a.name || "").localeCompare(b.name || ""); });
      return copy;
    }
    if (mode === "town") {
      copy.sort(function (a, b) { return (a.town || "").localeCompare(b.town || ""); });
      return copy;
    }
    copy.sort(function (a, b) {
      var sa = typeof a.score === "number" ? a.score : 0;
      var sb = typeof b.score === "number" ? b.score : 0;
      return sb - sa;
    });
    return copy;
  }

  function renderResults(data) {
    hideError();
    var sortMode = sortSelect ? sortSelect.value : "relevance";
    var results = sortResults(data.results || [], sortMode);
    var query = data.query || "";
    var scope = data.scope || "core";

    resultsSection.hidden = false;
    resultsPlaceholder.hidden = true;
    resultsTitle.textContent = t("resultsTitle");
    var scopeText = scope === "all" ? "including broader services" : "GP practices only";
    scopeText = scope === "all" ? t("scopeAll") : t("scopeCore");
    resultsMeta.textContent = results.length + " result" + (results.length === 1 ? "" : "s") + " " + t("found") + " \u201C" + query + "\u201D (" + scopeText + ")";

    if (results.length === 0) {
      resultsList.innerHTML = "";
      if (resultsEmptyText) {
        resultsEmptyText.textContent = t("noResults");
      }
      resultsEmpty.hidden = false;
      return;
    }

    resultsEmpty.hidden = true;
    resultsList.innerHTML = results.map(buildCard).join("");
  }

  function handleSearchResponse(res, myId) {
    if (myId !== searchSeq) {
      return Promise.resolve();
    }
    if (!res.ok) {
      var contentType = res.headers.get("Content-Type") || "";
      if (contentType.indexOf("application/json") !== -1) {
        return res.json().then(function (body) {
          if (myId !== searchSeq) return;
          showError(body.error || "Something went wrong. Please try again.");
          renderResults({ results: [], query: searchInput.value.trim() });
        });
      }
      showError("Search failed. Please try again.");
      renderResults({ results: [], query: searchInput.value.trim() });
      return Promise.resolve();
    }
    return res
      .json()
      .then(function (data) {
        if (myId !== searchSeq) return;
        latestResponse = data || { results: [], query: searchInput.value.trim() };
        renderResults(latestResponse);
      })
      .catch(function () {
        if (myId !== searchSeq) return;
        showError("Could not read search response. Please try again.");
        renderResults({ results: [], query: searchInput.value.trim() });
      });
  }

  function doSearch() {
    var q = searchInput.value.trim();
    if (!q) return;

    resultsSection.hidden = false;
    resultsPlaceholder.hidden = true;
    var myId = ++searchSeq;
    setLoading(true);

    var radiusEl = document.getElementById("radiusSelect");
    var radius = radiusEl ? radiusEl.value : "15";
    var scope = scopeToggle && scopeToggle.checked ? "all" : "core";
    var url = "/api/search?q=" + encodeURIComponent(q) + "&radius=" + encodeURIComponent(radius) + "&scope=" + encodeURIComponent(scope);
    fetch(url, { method: "GET", headers: { Accept: "application/json" } })
      .then(function (res) {
        if (myId !== searchSeq) {
          return null;
        }
        return handleSearchResponse(res, myId);
      })
      .catch(function () {
        if (myId !== searchSeq) {
          return;
        }
        showError("Network error. Please check your connection and try again.");
        renderResults({ results: [], query: q });
      })
      .finally(function () {
        if (myId === searchSeq) {
          setLoading(false);
        }
      });
  }

  function showVoiceStatus(message, isError) {
    if (!voiceStatus) return;
    voiceStatus.hidden = false;
    voiceStatus.textContent = message;
    voiceStatus.classList.toggle("error", !!isError);
  }

  function updateSpeechReadingUi(isReading) {
    if (speakResultsBtn) {
      speakResultsBtn.hidden = !!isReading;
    }
    if (stopSpeakBtn) {
      stopSpeakBtn.hidden = !isReading;
      stopSpeakBtn.textContent = t("stopReading");
      stopSpeakBtn.setAttribute("aria-label", t("stopReading"));
    }
  }

  function stopSpeechReading() {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    updateSpeechReadingUi(false);
  }

  function speakText(text) {
    if (!("speechSynthesis" in window) || !text) {
      return;
    }
    window.speechSynthesis.cancel();
    var utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1;
    utterance.pitch = 1;
    utterance.lang = SPEECH_LANG[currentLanguage()] || "en-GB";
    utterance.onstart = function () {
      updateSpeechReadingUi(true);
    };
    utterance.onend = utterance.onerror = function () {
      updateSpeechReadingUi(false);
    };
    window.speechSynthesis.speak(utterance);
  }

  function speakTopResults() {
    var results = Array.isArray(latestResponse.results) ? latestResponse.results : [];
    if (!results.length) {
      speakText("No results are currently available to read.");
      return;
    }
    var top = results.slice(0, 5);
    var summary = "Top results. " + top.map(function (item, idx) {
      var name = item.name || "Unknown practice";
      var town = item.town || "nearby area";
      var phone = item.telephone ? ". Phone " + item.telephone : "";
      return "Result " + (idx + 1) + ", " + name + ", " + town + phone;
    }).join(". ");
    speakText(summary);
  }

  function initialiseVoiceSearch() {
    if (!voiceSearchBtn) return;
    if (!SpeechRecognition) {
      voiceSearchBtn.disabled = true;
      showVoiceStatus(t("unsupportedVoice"), true);
      return;
    }
    recognition = new SpeechRecognition();
    recognition.lang = SPEECH_LANG[currentLanguage()] || "en-GB";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = function () {
      isListening = true;
      voiceSearchBtn.classList.add("active");
      showVoiceStatus(t("listening"), false);
    };
    recognition.onresult = function (event) {
      var transcript = event.results && event.results[0] && event.results[0][0] ? event.results[0][0].transcript : "";
      if (transcript) {
        searchInput.value = transcript.trim();
        showVoiceStatus(t("searchingFor") + " " + transcript.trim(), false);
        doSearch();
      }
    };
    recognition.onerror = function () {
      showVoiceStatus(t("voiceError"), true);
    };
    recognition.onend = function () {
      isListening = false;
      voiceSearchBtn.classList.remove("active");
    };

    voiceSearchBtn.addEventListener("click", function () {
      if (!recognition) return;
      if (isListening) {
        recognition.stop();
        return;
      }
      recognition.start();
    });
  }

  function setScopeMode(expanded) {
    if (scopeToggle) {
      scopeToggle.checked = expanded;
    }
    if (qualityPanel) {
      qualityPanel.classList.toggle("expanded", expanded);
    }
  }

  function saveScopeMode(expanded) {
    try {
      localStorage.setItem(SCOPE_STORAGE_KEY, expanded ? "all" : "core");
    } catch (e) {}
  }

  function loadScopeMode() {
    try {
      return localStorage.getItem(SCOPE_STORAGE_KEY) === "all";
    } catch (e) {
      return false;
    }
  }

  searchForm.addEventListener("submit", function (e) {
    e.preventDefault();
    doSearch();
  });

  var debounceTimer;
  searchInput.addEventListener("input", function () {
    clearTimeout(debounceTimer);
    var q = searchInput.value.trim();
    if (q.length < 2) {
      resultsSection.hidden = true;
      resultsPlaceholder.hidden = false;
      return;
    }
    debounceTimer = setTimeout(doSearch, 350);
  });

  if (sortSelect) {
    sortSelect.addEventListener("change", function () {
      renderResults(latestResponse);
    });
  }

  if (scopeToggle) {
    scopeToggle.addEventListener("change", function () {
      var expanded = !!scopeToggle.checked;
      setScopeMode(expanded);
      saveScopeMode(expanded);
      if (searchInput.value.trim().length >= 2) {
        doSearch();
      }
    });
  }

  if (qualityHelpBtn && qualityHelpText) {
    qualityHelpBtn.addEventListener("click", function () {
      var shouldShow = qualityHelpText.hidden;
      qualityHelpText.hidden = !shouldShow;
      qualityHelpBtn.setAttribute("aria-expanded", shouldShow ? "true" : "false");
    });
  }

  if (speakResultsBtn) {
    speakResultsBtn.addEventListener("click", speakTopResults);
  }

  if (stopSpeakBtn) {
    stopSpeakBtn.addEventListener("click", function () {
      stopSpeechReading();
    });
  }

  if (resultsList) {
    resultsList.addEventListener("click", function (event) {
      var button = event.target.closest(".card-read-btn");
      if (button) {
        var readText = [
          button.getAttribute("data-read-name") || "Practice",
          button.getAttribute("data-read-town") || "",
          button.getAttribute("data-read-phone") ? "Phone " + button.getAttribute("data-read-phone") : "",
        ].filter(Boolean).join(". ");
        speakText(readText);
        return;
      }
      var feedbackButton = event.target.closest("[data-feedback-type]");
      var ratingButton = event.target.closest("[data-rate]");
      if (!feedbackButton && !ratingButton) return;
      var fbType = feedbackButton ? feedbackButton.getAttribute("data-feedback-type") : "rating";
      var fbMessage = "";
      var fbRating = null;
      var practiceId = "";
      var practiceName = "";
      if (ratingButton) {
        fbRating = Number(ratingButton.getAttribute("data-rate"));
        practiceId = ratingButton.getAttribute("data-feedback-practice-id") || "";
        practiceName = ratingButton.getAttribute("data-feedback-practice-name") || "";
      } else {
        practiceId = feedbackButton.getAttribute("data-feedback-practice-id") || "";
        practiceName = feedbackButton.getAttribute("data-feedback-practice-name") || "";
      }
      if (fbType === "incorrect") {
        fbMessage = window.prompt(t("feedbackPrompt")) || "";
      }
      var ratingWrap = ratingButton ? ratingButton.closest(".star-rating") : null;
      if (ratingWrap && fbRating != null) {
        applyStarRatingVisual(ratingWrap, fbRating);
      }
      fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          type: fbType,
          rating: fbRating,
          query: latestResponse.query || "",
          scope: latestResponse.scope || "core",
          language: currentLanguage(),
          message: fbMessage,
          practice_id: practiceId,
          practice_name: practiceName,
        }),
      })
        .then(function (res) {
          if (!res.ok) {
            throw new Error("Feedback request failed");
          }
          return res.json().catch(function () {
            return {};
          });
        })
        .then(function () {
          if (ratingWrap && fbRating != null) {
            applyStarRatingVisual(ratingWrap, fbRating);
            var confirmation = ratingWrap.closest(".practice-feedback-row");
            confirmation = confirmation && confirmation.querySelector(".rating-confirmation");
            if (confirmation) {
              confirmation.textContent = "Thanks, rated " + fbRating + "/5";
            }
          }
          showVoiceStatus(t("feedbackThanks"), false);
        })
        .catch(function () {
          if (ratingWrap) {
            clearStarRatingVisual(ratingWrap);
            var confirmation = ratingWrap.closest(".practice-feedback-row");
            confirmation = confirmation && confirmation.querySelector(".rating-confirmation");
            if (confirmation) {
              confirmation.textContent = "";
            }
          }
          showVoiceStatus("Could not submit feedback right now.", true);
        });
    });
  }

  if (languageSelect) {
    try {
      var savedLang = localStorage.getItem(LANGUAGE_STORAGE_KEY);
      if (savedLang && I18N[savedLang]) {
        languageSelect.value = savedLang;
      }
    } catch (e) {}
    languageSelect.addEventListener("change", function () {
      try { localStorage.setItem(LANGUAGE_STORAGE_KEY, currentLanguage()); } catch (e) {}
      if (recognition) {
        recognition.lang = SPEECH_LANG[currentLanguage()] || "en-GB";
      }
      if (latestResponse && latestResponse.query) {
        renderResults(latestResponse);
      }
      if (speakResultsBtn) {
        speakResultsBtn.textContent = t("readTop");
      }
      if (stopSpeakBtn && !stopSpeakBtn.hidden) {
        stopSpeakBtn.textContent = t("stopReading");
        stopSpeakBtn.setAttribute("aria-label", t("stopReading"));
      }
    });
    if (speakResultsBtn) {
      speakResultsBtn.textContent = t("readTop");
    }
    if (stopSpeakBtn) {
      stopSpeakBtn.textContent = t("stopReading");
      stopSpeakBtn.setAttribute("aria-label", t("stopReading"));
    }
  }

  setScopeMode(loadScopeMode());
  initialiseVoiceSearch();
})();
