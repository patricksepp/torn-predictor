// ==UserScript==
// @name        Battle Stats Predictor (BSP) - REFERENCE ONLY
// @description ORIGINAAL TDup poolt - kasuta ainult referentsina meie TBSP skripti kirjutamisel
// @version     9.4.2
// @author      TDup (originaal) - referents TBSP projektile
// ==/UserScript==

// ============================================================
// TBSP ARENDAJALE: See fail on BSP originaalkood referentsiks.
// Ära muuda seda faili. Kasuta seda et mõista kuidas BSP töötab.
// Meie oma skript on: userscript/torn_predictor.user.js
// ============================================================

// #region LocalStorage võtmed - BSP kasutab neid
// Meie TBSP kasutab sarnast süsteemi aga oma namespace'iga: 'tbsp.'

const StorageKey = {
    PrimaryAPIKey: 'tdup.battleStatsPredictor.PrimaryAPIKey',
    IsPrimaryAPIKeyValid: 'tdup.battleStatsPredictor.IsPrimaryAPIKeyValid',
    PlayerId: 'tdup.battleStatsPredictor.PlayerId',
    IsEnabledOnOwnProfile: 'tdup.battleStatsPredictor.IsEnabledOnOwnProfile',
    BattleStatsAPIKey: 'tdup.battleStatsPredictor.BattleStatsApiKey',
    IsBattleStatsAPIKeyValid: 'tdup.battleStatsPredictor.IsBattleStatsApiKeyValid',
    PlayerBattleStats: 'tdup.battleStatsPredictor.playerBattleStats',
    IsAutoImportStats: 'tdup.battleStatsPredictor.IsAutoImportStats',
    AutoImportStatsLastDate: 'tdup.battleStatsPredictor.AutoImportStatsLastDate',
    BSPPrediction: 'tdup.battleStatsPredictor.cache.prediction.',
    TornStatsAPIKey: 'tdup.battleStatsPredictor.TornStatsApiKey',
    IsTornStatsAPIKeyValid: 'tdup.battleStatsPredictor.IsTornStatsApiKeyValid',
    TornStatsSpy: 'tdup.battleStatsPredictor.cache.spy_v2.tornstats_',
    IsAutoImportTornStatsSpies: 'tdup.battleStatsPredictor.tornstats_isAutoImportSpies',
    AutoImportLastDatePlayer: 'tdup.battleStatsPredictor.tornstats_AutoImportLastDatePlayer_',
    AutoImportLastDateFaction: 'tdup.battleStatsPredictor.tornstats_AutoImportLastDateFaction_',
    UploadDataAPIKey: 'tdup.battleStatsPredictor.UploadDataAPIKey',
    UploadDataAPIKeyIsValid: 'tdup.battleStatsPredictor.UploadDataAPIKeyIsValid',
    UploadDataLastUploadTime: 'tdup.battleStatsPredictor.UploadDataLastUploadTime',
    UploadDataIsAutoMode: 'tdup.battleStatsPredictor.UploadDataIsAutoMode',
    YataAPIKey: 'tdup.battleStatsPredictor.YataApiKey',
    IsYataAPIKeyValid: 'tdup.battleStatsPredictor.IsYataApiKeyValid',
    YataSpy: 'tdup.battleStatsPredictor.cache.spy_v2.yata_',
    DaysToUseSpies: 'tdup.battleStatsPredictor.DaysToUseTornStatsSpy',
    DateSubscriptionEnd: 'tdup.battleStatsPredictor.dateSubscriptionEnd',
    ShowPredictionDetails: 'tdup.battleStatsPredictor.showPredictionDetails',
    IsBSPEnabledOnPage: 'tdup.battleStatsPredictor.IsBSPEnabledOnPage_',
    ShouldOpenAttackURLInNewTab: 'tdup.battleStatsPredictor.ShouldOpenAttackURLInNewTab',
    IsShowingHonorBars: 'tdup.battleStatsPredictor.isShowingHonorBars',
    IsShowingAlternativeProfileDisplay: 'tdup.battleStatsPredictor.isShowingAlternativeProfileDisplay',
    BSPColorTheme: 'tdup.battleStatsPredictor.BspColorTheme',
    ColorStatsThreshold: 'tdup.battleStatsPredictor.ColorStatsThreshold_',
    IsShowingBattleStatsScore: 'tdup.battleStatsPredictor.IsShowingBattleStatsScore',
    IsShowingBattleStatsPercentage: 'tdup.battleStatsPredictor.IsShowingBattleStatsPercentage',
    IsClickingOnProfileStatsAttackPlayer: 'tdup.battleStatsPredictor.IsClickingOnProfileStatsAttackPlayer',
    IsHidingBSPOptionButtonInToolbar: 'tdup.battleStatsPredictor.IsHidingBSPOptionButtonInToolbar',
    HasSortByBSPButtonsOnFactionPage: 'tdup.battleStatsPredictor.HasSortByBSPButtonsOnFactionPage',
    AutoClearOutdatedCacheLastDate: 'tdup.battleStatsPredictor.AutoClearOutdatedCacheLastDate',
    TestLocalStorageKey: 'tdup.battleStatsPredictor.TestLocalStorage',
};

// #endregion

// #region TÄHTIS: Kuidas BSP otsustab kas kasutada API-t (oluline meie serverile)
function CanQueryAnyAPI() {
    // BSP ei tee päringuid kui leht pole fookuses - hea praktika mida peaksime jäljendama
    return document.visibilityState === "visible" && document.hasFocus();
}

// BSP server URL - meie asendame selle oma serveriga
function GetBSPServer() {
    return "http://www.lol-manager.com/api"; // MEIE: https://meie-server.railway.app/api
}
// #endregion

// #region Värvikoodide süsteem - KASUTA SEDA MEIE SKRIPTIS
const LOCAL_COLORS = [
    { maxValue: 5,           maxValueScore: 30,          color: '#949494', canModify: true },  // hall - väga nõrk
    { maxValue: 35,          maxValueScore: 70,          color: '#FFFFFF', canModify: true },  // valge - nõrk
    { maxValue: 75,          maxValueScore: 90,          color: '#73DF5D', canModify: true },  // roheline
    { maxValue: 125,         maxValueScore: 105,         color: '#47A6FF', canModify: true },  // sinine
    { maxValue: 400,         maxValueScore: 115,         color: '#FFB30F', canModify: true },  // oranž
    { maxValue: 10000000000, maxValueScore: 10000000000, color: '#FF0000', canModify: false }, // punane - ohtlik
];

// Staatuse koodid serveri vastusest
var FAIL = 0;
var SUCCESS = 1;
var TOO_WEAK = 2;
var TOO_STRONG = 3;
var MODEL_ERROR = 4;
var HOF = 5;       // Hall of Fame andmetest
var FFATTACKS = 6; // Fair Fight rünnakutest

var PREDICTION_VALIDITY_DAYS = 5; // Kui kaua cache kehtib
// #endregion

// #region Utility funktsioonid - hea referents

function JSONparse(str) {
    try { return JSON.parse(str); } catch (e) { }
    return null;
}

// BSP number formattimise funktsioon - kasuta seda meie skriptis
function FormatBattleStats(number) {
    var localized = number.toLocaleString('en-US');
    var myArray = localized.split(",");
    if (myArray.length < 1) return 'ERROR';

    var toReturn = myArray[0];
    if (number < 1000) return number;
    if (parseInt(toReturn) < 10) {
        if (parseInt(myArray[1][0]) != 0) {
            toReturn += '.' + myArray[1][0];
        }
    }
    switch (myArray.length) {
        case 2: toReturn += "k"; break;
        case 3: toReturn += "m"; break;
        case 4: toReturn += "b"; break;
        case 5: toReturn += "t"; break;
        case 6: toReturn += "q"; break;
    }
    return toReturn;
}

// Värvivalik TBS ratio põhjal
function GetColorMaxValueDifference(ratio) {
    for (var i = 0; i < LOCAL_COLORS.length; ++i) {
        if (ratio < LOCAL_COLORS[i].maxValue) {
            return LOCAL_COLORS[i].color;
        }
    }
    return "#ffc0cb";
}

// NPC ID-d mida ei peaks ennustama
function IsNPC(targetID) {
    switch (parseInt(targetID)) {
        case 4: case 7: case 8: case 9: case 10:
        case 15: case 17: case 19: case 20: case 21: case 23:
            return true;
        default: return false;
    }
}

function FormatRelativeTime(date) {
    let diff = Math.round((new Date() - date) / 1000);
    if (diff < 60) return 'Seconds ago';
    if (diff < 3600) return Math.floor(diff/60) + ' minutes ago';
    if (diff < 86400) return Math.floor(diff/3600) + ' hours ago';
    return Math.floor(diff/86400) + ' days ago';
}
// #endregion

// #region Cache loogika - BSP kasutab localStorage, meie kasutame sama + server cache

function GetPredictionFromCache(playerId) {
    var key = StorageKey.BSPPrediction + playerId;
    if (localStorage[key] == "[object Object]") localStorage.removeItem(key);
    if (localStorage[key] != undefined) return JSON.parse(localStorage[key]);
    return undefined;
}

function SetPredictionInCache(playerId, prediction) {
    if (prediction.Result == FAIL || prediction.Result == MODEL_ERROR) return;
    var key = StorageKey.BSPPrediction + playerId;
    try { localStorage[key] = JSON.stringify(prediction); }
    catch (e) { console.log("Cache error: " + e); }
}

// TÄHTIS: Kuidas BSP otsustab kas näidata spy vs ennustus
function GetMostRecentSpyFromCache(playerId) {
    let tornStatsSpy = GetTornStatsSpyFromCache(playerId);
    let yataSpy = GetSpyFromYataCache(playerId);
    if (tornStatsSpy == undefined && yataSpy == undefined) return undefined;
    if (tornStatsSpy == undefined) return yataSpy;
    if (yataSpy == undefined) return tornStatsSpy;
    return yataSpy.timestamp >= tornStatsSpy.timestamp ? yataSpy : tornStatsSpy;
}
// #endregion

// #region Peamine ennustuse loogika - KRIITILINE OSA

async function GetPredictionForPlayer(targetId, callback) {
    if (targetId == undefined || targetId < 1) return;
    if (IsNPC(targetId) == true) return;

    // 1. Kontrolli spy cache (kui värskes)
    let targetSpy = GetMostRecentSpyFromCache(targetId);
    if (targetSpy != undefined && targetSpy.total != undefined && targetSpy.total != 0) {
        let spyDateConsideredTooOld = new Date();
        let daysToUseSpies = parseInt(GetStorage(StorageKey.DaysToUseSpies));
        spyDateConsideredTooOld.setDate(spyDateConsideredTooOld.getDate() - daysToUseSpies);
        let spyDate = new Date(targetSpy.timestamp * 1000);
        if (spyDate > spyDateConsideredTooOld) {
            callback(targetId, targetSpy); // Kasuta spy andmeid
            return;
        }
    }

    // 2. Kontrolli ennustuse cache
    var prediction = GetPredictionFromCache(targetId);
    if (prediction != undefined) {
        var expirationDate = new Date();
        expirationDate.setDate(expirationDate.getDate() - PREDICTION_VALIDITY_DAYS);
        var predictionDate = new Date(prediction.DateFetched || prediction.PredictionDate);

        if (predictionDate > expirationDate) {
            prediction.fromCache = true;
            if (targetSpy != undefined) prediction.attachedSpy = targetSpy;
            callback(targetId, prediction);
            return;
        }
        localStorage.removeItem(StorageKey.BSPPrediction + targetId);
    }

    // 3. Päri serverist
    console.log("Querying BSP server for target " + targetId);
    const newPrediction = await FetchScoreAndTBS(targetId); // BSP server call
    if (newPrediction != undefined) {
        newPrediction.DateFetched = new Date();
        SetPredictionInCache(targetId, newPrediction);
    }
    if (targetSpy != undefined && newPrediction != undefined) {
        newPrediction.attachedSpy = targetSpy;
    }
    callback(targetId, newPrediction);
}
// #endregion

// #region Lehel inject - kuidas BSP leiab torn ID-d

// PageType enum - millised lehed on toetatud
const PageType = {
    Profile: 'Profile',
    HallOfFame: 'Hall Of Fame',
    Faction: 'Faction',
    Bounty: 'Bounty',
    Hospital: 'Hospital',
    Forum: 'Forum',
    Attack: 'Attack',
    War: 'War',
    // ... jne (vaata täielikku loendit originaalist)
};

// Kuidas BSP inject töötab lehel - leiab mängija nimed ja lisab badge
// 1. MutationObserver - vaatab DOM muutusi (Torn on SPA)
// 2. Leiab .user.name elementid
// 3. Parsib torn ID href'ist
// 4. Kutsub GetPredictionForPlayer()
// 5. Lisab värvilise iconStats div'i

// Grid badge inject (kõikidel lehtedel v.a profiil)
function OnPlayerStatsRetrievedForGrid(targetId, prediction) {
    var urlAttack = "https://www.torn.com/loader.php?sid=attack&user2ID=" + targetId;
    
    // Leiab div'id kus inject toimub
    // dictDivPerPlayer[targetId] = array of DOM elements
    
    let localBattleStats = GetLocalBattleStats(); // Kasutaja enda statsid
    let consolidatedData = GetConsolidatedDataForPlayerStats(prediction);
    
    // Arvutab värvi
    let tbsRatio = 100 * consolidatedData.TargetTBS / localBattleStats.TBS;
    let colorComparedToUs = GetColorMaxValueDifference(tbsRatio);
    let formattedBattleStats = FormatBattleStats(consolidatedData.TargetTBS);

    // Inject HTML
    // isShowingHonorBars = true → position:absolute inject
    // isShowingHonorBars = false → inline inject
    let toInject = '<a href="' + urlAttack + '" target="_blank">' +
        '<div style="position:absolute;z-index:100;margin:-10px -9px">' +
        '<div class="iconStats" style="background:' + colorComparedToUs + '">' + 
        formattedBattleStats + '</div></div></a>';
    
    // dictDivPerPlayer[targetId][i].innerHTML = toInject + existingContent;
}

// Profiilileht - eraldi suurem display
function OnProfilePlayerStatsRetrieved(playerId, prediction) {
    // Loob tabeli: TBS | % You | FF | Source | Date
    // Lisab PlayerProfileDivWhereToInject div'ile
    // Näide väljundist:
    // +--------+-------+------+--------+----------+
    // | TBS    | % You | FF   | Source | Date     |
    // +--------+-------+------+--------+----------+
    // | 28.4m  | 87%   | 2.31 | [icon] | 2d ago   |
    // +--------+-------+------+--------+----------+
}
// #endregion

// #region DOM manipulation - kuidas BSP leiab ID-d erinevatelt lehtedelt

// NÄIDE: Kuidas BSP leiab torn ID profiililehelt
// window.location.href = "https://www.torn.com/profiles.php?XID=123456"
// ProfileTargetId = new URLSearchParams(window.location.search).get('XID')

// NÄIDE: Kuidas BSP kasutab MutationObserver'it
// Torn on React SPA - leht ei laadi uuesti, DOM muutub
// BSP kasutab MutationObserver et tuvastada uued .user.name elemendid

// NÄIDE: Kuidas BSP parsib torn ID href'ist
// element.querySelector('a[href*="XID="]')
// href.match(/XID=(\d+)/)[1]

// #endregion

// #region Settings UI - kuidas BSP settings paneel töötab

// BSP avab settings paneeli profiililehel "BSP Settings" nupuga
// Paneel on tab-põhine:
// - Profile tab: API võti + subscriptsioon
// - Settings tab: enda statsid + värvid
// - Pages tab: mis lehtedel näidata
// - TornStats tab: TornStats API
// - YATA tab: YATA API  
// - Upload Data tab: rünnakulogide upload
// - Debug tab: cache info

// MEIE TBSP settings UI peaks olema sarnane aga lihtsam:
// - API võti
// - Subscriptsioon info
// - Värvid
// - Lehed kus näidata
// #endregion

// #region Subscriptsioon kontroll

function IsSubscriptionValid() {
    let subscriptionEnd = localStorage[StorageKey.DateSubscriptionEnd];
    if (subscriptionEnd == undefined) return true; // Uus kasutaja - tasuta nädal
    
    var dateNow = new Date();
    var dateSubscriptionEnd = new Date(subscriptionEnd);
    return (dateSubscriptionEnd - dateNow) > 0;
}

// BSP küsib subscriptsioon info serverist pärast API võtme valideerimist
// Server tagastab: { subscriptionEnd: "2026-05-01T00:00:00Z" }
// Userscript salvestab selle localStorage'isse
// #endregion
